import _thread
from operator import itemgetter
import telebot
import config
import time
from functools import reduce
import random

if __name__ == '__main__':
    bot = telebot.TeleBot(config.token)
    data = {}


    @bot.message_handler(commands=['play', 'Play'])
    def start_game_from_command(message: telebot.types.Message):

        if message.chat.id not in data.keys() or data[message.chat.id]['is_stopped']:
            start_game(message.chat.id, quest=generate_q())
        else:
            bot.reply_to(message, "Руки на стол!! Раунд уже запущен")


    @bot.message_handler(func=lambda message: True, content_types=['text'])
    def add_answer_or_quest_from_message(message: telebot.types.Message):
        if message.chat.id in data.keys() and len(message.text) < 100:
            chat_id = message.chat.id
            game_data = data[chat_id]
            abbreviation = reduce(lambda a, b: a + b[0], [''] + message.text.split())
            if abbreviation.lower() == game_data['quest']:
                add_answer(message)
            if time.time() > game_data["end_voting"] and game_data['last_winner']:
                if message.from_user.id == game_data["last_winner"].id and len(message.text) == 3:
                    final_update_quest_message(chat_id)
                    start_game(chat_id, message.text.lower())
                    data[chat_id]["last_winner"] = message.from_user


    def final_update_quest_message(chat_id):
        game_data = data[chat_id]
        winner = game_data['last_winner']
        win_abb = f"<b>{game_data['win_answer']}</b>"
        link_to_winner = f"<a href='tg://user?id={winner.id}'>{winner.full_name}</a>"
        bot.edit_message_text(text=game_data["quest_message"].text + f"\nПобедитель - {link_to_winner} c его {win_abb}",
                              chat_id=chat_id,
                              message_id=game_data['quest_message'].message_id,
                              parse_mode='HTML')
        bot.delete_message(chat_id, data[chat_id]["win_message"].id)


    def add_answer_to_quest_message(game_data, message):
        quest_message = game_data['quest_message']
        new_quest_message = quest_message.text + f"\n<a href='tg://user?id={message.from_user.id}'>" \
                                                 f"{message.from_user.full_name}</a>: <b>{message.text}</b>"
        bot.edit_message_text(new_quest_message, message.chat.id, quest_message.message_id, parse_mode='HTML')
        game_data['quest_message'].text = new_quest_message
        bot.delete_message(message.chat.id, message.message_id)


    def start_game(chat_id, quest):
        message = f"Задание: <b>{quest.upper()}</b>. У вас есть {config.wait_answers_time} " \
                  f"секунд, чтобы прислать ваши ответы!Поехали!\n)"
        data[chat_id] = {
            "start": int(time.time()),
            "is_wait_answers": True,
            "is_voting": False,
            "is_stopped": False,
            "poll": None,
            "end_answers": int(time.time() + config.wait_answers_time),
            "end_voting": int(time.time() + config.wait_answers_time + config.vote_time),
            "quest": quest,
            "quest_message": bot.send_message(chat_id, message, parse_mode='HTML'),
            "answers": {},
            "last_winner": None,
            "win_message": None,
            "win_answer": None
        }


    def add_answer(message):
        game_data = data[message.chat.id]
        if game_data['last_winner'] and message.from_user.id == game_data['last_winner'].id:
            bot.reply_to(message, "Эй, ты загадывал. Отдохни до следующего раунда!")
            return
        elif not game_data["is_wait_answers"]:
            bot.reply_to(message, 'Ты опоздал. Подожди начала следующего раунда!')
            return
        elif message.text.lower() in game_data["answers"].keys():
            bot.reply_to(message, "Такой ответ уже был принят")
            return

        else:
            game_data["answers"][message.text.lower()] = message.from_user
            add_answer_to_quest_message(game_data, message)
            if len(game_data["answers"]) == 10:
                bot.send_message(message.chat.id,
                                 "Вы, скорострелы, накидали уже 10 ответов и больше в меня не влезет. Заканчиваю раунд")
                game_data["end_answers"] = int(time.time())
                game_data["end_voting"] = int(time.time() + config.vote_time)


    def start_voting(chat_id):
        game_data = data[chat_id]
        answers = list(game_data['answers'].keys())
        if len(answers) >= config.min_answers_for_start_voting:
            poll = bot.send_poll(chat_id=chat_id,
                                 question=f"Голосуем за лучший ответ! Задание - {game_data['quest']}",
                                 is_anonymous=config.is_anonimous_polls,
                                 allows_multiple_answers=config.is_allows_multiple_answers,
                                 options=answers,
                                 reply_to_message_id=game_data['quest_message'].id)

            game_data["is_wait_answers"] = False
            game_data["is_voting"] = True
            game_data["poll"] = poll.message_id
        else:
            bot.send_message(chat_id, "Никто не хочет играть. Я спать. Для начала новой игры введите '/Play'")
            data[chat_id]["is_wait_answers"] = False
            data[chat_id]["is_stopped"] = True


    def end_round(chat_id: str):
        game_data = data[chat_id]
        poll = bot.stop_poll(chat_id, game_data["poll"])
        game_data["is_voting"] = False
        sorted_answers = sorted([(option.text, option.voter_count) for option in poll.options],
                                reverse=True,
                                key=itemgetter(1))

        if poll.total_voter_count < config.min_votes_for_complete_quest:
            bot.send_message(chat_id, "Слишком мало голосов. Старайтесь лучше! Я спать.\n"
                                      "Для начала новой игры введите '/Play'")
            game_data['is_stopped'] = True
            return
        elif sorted_answers[0][1] == sorted_answers[1][1]:
            bot.send_message(chat_id, "Раунд закончен. Победила дружба!\nОтвратительно.\nВерните в чат ненависть! "
                                      "А я пока спать. Для начала новой игры введите '/Play'")
            game_data['is_stopped'] = True
            return
        else:
            best_answer = sorted_answers[0][0]
            winner = game_data["answers"][best_answer]
            time.sleep(3)
            game_data["last_winner"] = winner
            game_data["win_answer"] = best_answer.upper()
            win_message = f"Победитель - <a href='tg://user?id={winner.id}'>{winner.full_name} </a>c его " \
                          f"{best_answer.upper()}\nУ тебя есть {config.winner_time} секунд для того, чтобы придумать " \
                          f"задание, или это сделаю я!"
            game_data["win_message"] = bot.send_message(chat_id, win_message, parse_mode='HTML')


    def generate_q():
        quest = ''
        for i in range(3):
            quest += random.choice(config.frequency)
        return quest


    def check_status(data):
        while True:
            try:
                time.sleep(1)
                print(data)
                timestamp = int(time.time())
                if data.keys():
                    for chat_id in list(data.keys()):
                        game_data = data[chat_id]
                        if timestamp > game_data["end_answers"] and game_data["is_wait_answers"]:
                            start_voting(chat_id)
                        elif timestamp > game_data["end_voting"] and game_data["is_voting"]:
                            end_round(chat_id)
                        elif timestamp > game_data["end_voting"] + config.winner_time and not game_data['is_stopped']:
                            final_update_quest_message(chat_id)
                            start_game(chat_id, quest=generate_q())
            finally:
                pass


    _thread.start_new_thread(check_status, (data,))
    bot.polling(none_stop=True, interval=1, )
