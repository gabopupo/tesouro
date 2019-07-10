import telegram.ext as tex
import logging as log


def start(bot, update):
    text = open("start.txt", "r").read()
    bot.send_message(chat_id=update.message.chat_id, text=text)

def main():
    updater = tex.Updater(token=token)
    dispatcher = updater.dispatcher

    log.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=log.INFO)

    dispatcher.add_handler(tex.CommandHandler('start', start))

    updater.start_polling()

if __name__ == "__main__":
    main()

