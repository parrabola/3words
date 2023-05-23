import _thread
from operator import itemgetter
import telebot
from telebot import types
import config
import time
from functools import reduce
import random

if __name__ == '__main__':
    bot = telebot.TeleBot(config.token)
    data = {}
    pre_start_data = {}


    @bot.message_handler(commands=['play', 'Play'])
    def start_game_from_command(message: telebot.types.Message):
        if not data.get(message.chat.id):
            trigger_start_button(message.chat.id, message)
            return
        else:
            bot.reply_to(message, "Руки на стол!! Раунд уже запущен")


    @bot.message_handler(func=lambda message: True, content_types=['text'])
    def add_answer_or_quest_from_message(message: telebot.types.Message):
        game_data = data.get(message.chat.id)
        last_winner = data.get(message.chat.id, {}).get('winner')
        if game_data and get_abbreviation(message) == game_data['quest']:
            add_answer(message, game_data)
        elif last_winner and (last_winner['user'].id, len(message.text)) == (message.from_user.id, 3):
            add_winner_to_quest_message(message.chat.id)
            start_game(message.chat.id, message.text)


    @bot.callback_query_handler(func=lambda call: True)
    def send_trigger_to_start(call):
        if call.data == 'trigger_start_button_3words' + str(call.message.chat.id):
            trigger_start_button(call.message.chat.id, call)


    def stop_game(chat_id, reason):
        bot.send_message(chat_id, "Конец игры: " + reason + " Я спать. Для начала новой игры введите '/play'")
        data[chat_id].clear()


    def get_abbreviation(message):
        return reduce(lambda a, b: a + b[0], [''] + message.text.split()).lower()


    def add_winner_to_quest_message(chat_id):
        game_data = data[chat_id]
        winner = game_data["winner"]
        win_abb = f"<b>{game_data['winner']['answer']}</b>"
        link_to_winner = get_link_to_user(winner['user'])
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


    def trigger_start_button(chat_id, message):
        if chat_id not in pre_start_data:
            pre_start_data[chat_id] = {"waiting_players": {}}
            keyboard = generate_start_button(chat_id)
            pre_start_data[chat_id]["button"] = bot.send_message(chat_id=chat_id,
                                                                 text=f"Запускается ожидание игроков",
                                                                 reply_markup=keyboard,
                                                                 parse_mode='HTML')
        elif message.from_user.id in pre_start_data[chat_id]["waiting_players"]:
            return remove_user_from_pre_start(chat_id, message.from_user.id)
        elif type(message) == telebot.types.Message:
            link_to_start_button = f"href='https://t.me/c/{str(chat_id).replace('-100', '')}/" \
                                   f"{pre_start_data[chat_id]['button'].id}'"
            bot.reply_to(message,
                         text=f"Я добавил тебя в <a {link_to_start_button}>Список ожидающих</a>.",
                         parse_mode="HTML")
        add_waiting_user(chat_id, message.from_user)


    def add_waiting_user(chat_id, user):
        pre_start_data[chat_id]["waiting_players"][user.id] = {"time": int(time.time()), "user": user}
        update_start_button_message_text(chat_id)


    def update_start_button_message_text(chat_id):
        waiting_users = pre_start_data[chat_id]["waiting_players"]
        waiting_users_str = "Никого. Нажми на кнопку!" if not waiting_users else ','.join(
            ["\n" + get_link_to_user(waiting_users[user]['user']) for user in waiting_users])
        keyboard = generate_start_button(chat_id)
        bot.edit_message_text(chat_id=chat_id, message_id=pre_start_data[chat_id]["button"].id,
                              text='В ожидании сейчас: \n' + waiting_users_str,
                              reply_markup=keyboard,
                              parse_mode='HTML')


    def get_link_to_user(user):
        return f"<a href='tg://user?id={user.id}'>{user.full_name}</a> "


    def remove_user_from_pre_start(chat_id, user):
        pre_start_data[chat_id]["waiting_players"].pop(user)
        update_start_button_message_text(chat_id)
        if not len(pre_start_data[chat_id]["waiting_players"]):
            remove_start_button(chat_id)
            pre_start_data .pop(chat_id)


    def remove_start_button(chat_id):
        bot.delete_message(chat_id, pre_start_data[chat_id]["button"].id)


    def generate_start_button(chat_id):
        count = config.min_players_count - len(pre_start_data[chat_id]["waiting_players"])
        var = "тык"
        if str(count)[-1] in ["2", "3", "4"] and str(count)[0] != "1":
            var += 'a'
        elif str(count)[-1] != "1":
            var += 'ов'
        start_button = types.InlineKeyboardButton(
            text=f'До начала игры {count} {var}',
            callback_data='trigger_start_button_3words' + str(chat_id))
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(start_button)
        return keyboard


    def start_game(chat_id, quest):
        message = f"Задание: <b>{quest.upper()}</b>. У вас есть {config.wait_answers_time} " \
                  f"секунд, чтобы прислать ваши ответы!Поехали!\n\n"
        data[chat_id] = {
            "start": int(time.time()),
            "is_wait_answers": True,
            "is_voting": False,
            "winner": False,
            "poll": None,
            "end_answers": int(time.time() + config.wait_answers_time),
            "end_voting": int(time.time() + config.wait_answers_time + config.vote_time),
            "quest": quest.lower(),
            "quest_message": bot.send_message(chat_id, message, parse_mode='HTML'),
            "answers": {},
            "win_message": None
        }


    def add_answer(message, game_data):
        if not game_data["is_wait_answers"]:
            bot.reply_to(message, 'Ты опоздал. Подожди начала следующего раунда!')
            return
        elif message.text in game_data["answers"]:
            bot.reply_to(message, "Такой ответ уже был принят")
            return
        elif len(message.text) > 99:
            bot.reply_to(message, "Невпихуемое")
            return
        else:
            game_data["answers"][message.text] = message.from_user
            add_answer_to_quest_message(game_data, message)
            if len(game_data["answers"]) == 10:
                bot.send_message(message.chat.id, "Принят десятый ответ. Вы - скорострелы. Начинаю голосование")
                game_data["end_answers"] = int(time.time())
                game_data["end_voting"] = int(time.time() + config.vote_time)


    def start_voting(chat_id):
        game_data = data[chat_id]
        answers = list(game_data['answers'].keys())
        if len(answers) >= config.min_answers_for_start_voting:
            poll = bot.send_poll(chat_id=chat_id,
                                 question=f"Голосуем за лучший ответ! {config.vote_time} секунд на голосование."
                                          f" Задание - {game_data['quest']}",
                                 is_anonymous=config.is_anonimous_polls,
                                 allows_multiple_answers=config.is_allows_multiple_answers,
                                 options=answers,
                                 reply_to_message_id=game_data['quest_message'].id)

            game_data["is_wait_answers"] = False
            game_data["is_voting"] = True
            game_data["poll"] = poll.message_id
        else:
            stop_game(chat_id, "Никто не хочет играть.")


    def end_round(chat_id: str):
        game_data = data[chat_id]
        poll = bot.stop_poll(chat_id, game_data["poll"])
        game_data["is_voting"] = False
        sorted_answers = sorted([(option.text, option.voter_count) for option in poll.options],
                                reverse=True,
                                key=itemgetter(1))
        if poll.total_voter_count < config.min_votes_for_complete_quest:
            stop_game(chat_id, "Слишком мало голосов.")
            return
        elif sorted_answers[0][1] == sorted_answers[1][1]:
            bot.send_message(chat_id, "Раунд закончен. Победила дружба!\nОтвратительно.\nВерните в чат ненависть! "
                                      "Начинаю новую игру")
            start_game(chat_id, quest=generate_quest())
            return
        else:
            best_answer = sorted_answers[0][0]
            winner = game_data["answers"][best_answer]
            win_message_text = f"Победитель - <a href='tg://user?id={winner.id}'>{winner.full_name} </a>c его " \
                               f"{best_answer.upper()}\nУ тебя есть {config.winner_time} секунд для того, чтобы " \
                               f"придумать задание, или это сделаю я!"
            game_data["winner"] = {'user': winner, 'answer': best_answer.upper()}
            game_data["win_message"] = bot.send_message(chat_id, win_message_text, parse_mode='HTML')


    def generate_quest():
        quest = ''
        for i in range(3):
            quest += random.choice(config.frequency)
        return quest


    def check_pre_start_status(start_data):
        while True:
            try:
                time.sleep(1)
                print(start_data)
                for chat_id in list(start_data.keys()):
                    if len(start_data[chat_id]["waiting_players"]) >= config.min_players_count:
                        start_game(chat_id, quest=generate_quest())
                        users_str = ''
                        for user in start_data[chat_id]["waiting_players"]:
                            users_str += get_link_to_user(start_data[chat_id]["waiting_players"][user]['user'])
                        bot.send_message(chat_id, users_str + "игра начинается", parse_mode='HTML')
                        remove_start_button(chat_id)
                        start_data.pop(chat_id)
                    else:
                        users = start_data[chat_id]["waiting_players"]
                        for user in list(users.keys()):
                            if start_data[chat_id]["waiting_players"][user]['time'] < int(
                                    time.time()) - config.user_game_waiting_time:
                                remove_user_from_pre_start(chat_id, user)
            finally:
                pass


    def check_status(games):
        while True:
            try:
                time.sleep(1)
                print(games)
                timestamp = int(time.time())
                for chat_id in list(games.keys()):
                    game_data = games[chat_id]
                    if not game_data:
                        break
                    elif timestamp > game_data["end_answers"] and game_data["is_wait_answers"]:
                        start_voting(chat_id)
                    elif timestamp > game_data["end_voting"] and game_data["is_voting"]:
                        end_round(chat_id)
                    elif timestamp > game_data["end_voting"] + config.winner_time and game_data['winner']:
                        add_winner_to_quest_message(chat_id)
                        start_game(chat_id, quest=generate_quest())
            finally:
                pass


    _thread.start_new_thread(check_status, (data,))
    _thread.start_new_thread(check_pre_start_status, (pre_start_data,))
    bot.polling(none_stop=True, interval=1, )
