import telegram as t
import telegram.ext as tex
import logging as log
import uuid

payments = []
debts = []

def start(update: t.Update, context: tex.CallbackContext):
    text = open("start.txt", "r").read()
    update.message.reply_text(text)

def addPay(update: t.Update, context: tex.CallbackContext):
    paymentName, paymentValue = context.args
    payments.append({ 'id': uuid.uuid4(), 'name': paymentName, 'value': paymentValue })
    text = "O pagamento "+paymentName+" de valor R$"+str(paymentValue)+" foi adicionado."
    update.message.reply_text(text)

def addDebt(update: t.Update, context: tex.CallbackContext):
    payer, payee, debtValue = context.args
    debts.append({ 'id': uuid.uuid4(), 'payer': payer, 'payee': payee, 'value': debtValue })
    text = "A dívida de "+payer+" a "+payee+" de valor R$"+str(debtValue)+" foi adicionada."
    update.message.reply_text(text)

def showAllPays(update: t.Update, context: tex.CallbackContext):
    out = ""
    for i, p in enumerate(payments):
        out += str(i)+" "+p['name']+": "+p['value']+"\n"
    update.message.reply_text(out)

def showAllDebts(update: t.Update, context: tex.CallbackContext):
    out = ""
    for i, p in enumerate(debts):
        out += str(i)+" "+p['payer']+" -> "+p['payee']+": "+p['value']+"\n"
    update.message.reply_text(out)

def main():
    updater = tex.Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    log.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=log.INFO)

    dispatcher.add_handler(tex.CommandHandler('start', start))
    dispatcher.add_handler(tex.CommandHandler('add_pay', addPay))
    dispatcher.add_handler(tex.CommandHandler('add_debt', addDebt))
    dispatcher.add_handler(tex.CommandHandler('show_pays', showAllPays))
    dispatcher.add_handler(tex.CommandHandler('show_debts', showAllDebts))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

