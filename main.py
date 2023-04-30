from operator import itemgetter
import telebot
import config
import time
from functools import reduce

if __name__ == '__main__':
    bot = telebot.TeleBot(config.token)
    data = {
        "12312123": {
            "start": 123465798,
            "is_wait_answers": True,
            "is_voting": False,
            "end_answers": 123124,
            "end_voting": 1231244,
            "quest": 'asd',
            "poll": 3112323,
            "answers": {
                "asymptotic stylish data": 12312312,
                "anal stylish data": 12312312,
                "anal stylish dristy": 12312344
            },
            "last_winner": 23423332
        }
    }


    @bot.message_handler(commands=['play'])
    def start_game_from_command(message: telebot.types.Message):
        if message.chat.id not in data.keys():
            start_game(message.chat.id, quest=generate_q())
        else:
            bot.reply_to(message, "Руки на стол!! Раунд уже запущен")


    @bot.message_handler(func=lambda message: True, content_types=['text'])
    def add_answer_from_message(message: telebot.types.Message):
        chat_id = message.chat.id
        if chat_id in data.keys():
            abbreviation = reduce(lambda a, b: a + b[0], [''] + message.text.split())
            if abbreviation.lower() == data[chat_id]['quest']:
                add_answer(message)


    @bot.message_handler(func=lambda message: True, content_types=['text'])
    def start_quest_from_last_winner(message: telebot.types.Message):
        chat_id = message.chat.id
        if data[chat_id] and time.time() > data[chat_id]["end_voting"]:
            if message.from_user.id == data[chat_id]["last_winner"] and len(message.text) == 3:
                quest = message.text.lower()
                start_game(chat_id, quest)
                data[chat_id]["last_winner"] = message.from_user.id


    def start_game(chat_id, quest):
        data[chat_id] = {
            "start": int(time.time()),
            "is_wait_answers": True,
            "is_voting": False,
            "poll": None,
            "end_answers": int(time.time() + config.wait_answers_time),
            "end_voting": int(time.time() + config.wait_answers_time + config.vote_time),
            "quest": quest,
            "answers": {},
            "last_winner": None
        }

        bot.send_message(chat_id, f"Задание: {quest}. У вас есть {config.wait_answers_time} секунд,"
                                  f" чтобы прислать ваши ответы!\nПоехали!")


    def add_answer(message):
        chat_id = message.chat.id
        if message.from_user.id == data[chat_id]['last_winner']:
            bot.reply_to(message, "Эй, ты загадывал. Отдохни до следующего раунда!")
            return
        if not data[chat_id]["is_wait_answers"]:
            bot.reply_to(message, 'Ты опоздал. Подожди начала следующего раунда!')
            return
        if message.text.lower() in data["answers"].keys():
            bot.reply_to(message, "Такой ответ уже был принят")
            return
        data[chat_id]["answers"][message.text.lower()] = message.from_user.id


    def start_voting(chat_id):
        answers = data[chat_id]['answers'].keys()
        if len(answers) > config.min_answers_for_start_voting:
            poll = bot.send_poll(chat_id=chat_id,
                                 question=f"Голосуем за лучший ответ! Задание - {data[chat_id]['quest']}",
                                 is_anonymous=config.is_anonimous_polls,
                                 allows_multiple_answers=config.is_allows_multiple_answers,
                                 options=answers)

            data[chat_id]["is_wait_answers"] = False
            data[chat_id]["is_voting"] = True
            data[chat_id]["poll"] = poll.message_id
        else:
            bot.send_message(chat_id, "Никто не хочет играть. Я спать. Для начала новой игры введите '/Play'")
            data.pop(chat_id)


    def end_round(chat_id: str):
        poll = bot.stop_poll(chat_id, data[chat_id]["poll"])
        data[chat_id]['is_voting'] = False

        if poll.total_voter_count < config.min_votes_for_complete_quest:
            bot.send_message(chat_id, "Слишком мало голосов. Старайтесь лучше! Я спать.\n"
                                      "Для начала новой игры введите '/Play'")
            data.pop(chat_id)
            return

        sorted_answers = sorted([(option.text, option.voter_count) for option in poll.options],
                                reverse=True,
                                key=itemgetter(1))

        if sorted_answers[0][1] == sorted_answers[1][1]:
            bot.send_message(chat_id, "Раунд закончен. Победила дружба!\nОтвратительно.\nВерните в чат ненависть! "
                                      "А я пока спать. Для начала новой игры введите '/Play'")
            data.pop(chat_id)
            return

        best_answer = sorted_answers[0][0]
        winner = data[chat_id]["answers"][best_answer]
        data[chat_id]["last_winner"] = winner
        bot.send_message(chat_id, f"Победитель - tg://user?id=<{winner}> c его {best_answer.upper()}\nУ тебя есть "
                                  f"{config.winner_time} секунд для того, чтобы придумать задание, или это сделаю я!",
                         parse_mode="MarkdownV2")


    # Это допишется позже
    def generate_q():
        return "AAA"


    def check_status(data):
        timestamp = int(time.time())
        if data.keys():
            for chat_id in data.keys():
                if timestamp > data[chat_id]["end_answers"] and data[chat_id]["is_wait_answers"]:
                    start_voting(chat_id)
                    return
                if timestamp > data[chat_id]["end_voting"] and data[chat_id]["is_voting"]:
                    end_round(chat_id)
                    return
                if timestamp > data[chat_id]["end_voting"] + config.winner_time:
                    start_game(chat_id, quest=generate_q())


    # Это заменится тредом
    while True:
        check_status(data)
        time.sleep(1)
