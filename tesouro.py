import telegram as t
import telegram.ext as tex
import logging as log
import uuid

END, FIRST, SECOND = range(-1, 2)
people = []
payments = []
debts = []

# inicializa o bot
def start(update: t.Update, context: tex.CallbackContext):
    text = open("start.txt", "r").read()
    update.message.reply_text(text)

def toLower(s):
    s = str(s)
    return s.lower()

# adiciona uma pessoa no orçamento
def addPerson(update: t.Update, context: tex.CallbackContext):
    tHandle, alias = context.args
    people.append({ 'id': uuid.uuid4(), 'handle': tHandle, 'alias': toLower(alias) })
    text = tHandle+" foi adicionado(a)."
    update.message.reply_text(text)
    
# adiciona um pagamento
def addPay(update: t.Update, context: tex.CallbackContext):
    paymentName, paymentValue = context.args
    payments.append({ 'id': uuid.uuid4(), 'name': paymentName, 'value': paymentValue })
    text = "O pagamento "+paymentName+" de valor R$"+str(paymentValue)+" foi adicionado."
    update.message.reply_text(text)

def exists(person):
    return (any(person == p['alias'] for p in people) or any(person == p['handle'] for p in people))

# adiciona uma dívida
def addDebt(update: t.Update, context: tex.CallbackContext):
    payer, payee, debtValue = context.args
    payer, payee = toLower(payer), toLower(payee)
    if exists(payer) and exists(payee):
        debts.append({ 'id': uuid.uuid4(), 'payer': payer, 'payee': payee, 'value': debtValue, 'bound_payment': None })
    
        decision = [["Sim", "Não"]]
        reply_markup = t.ReplyKeyboardMarkup(decision, one_time_keyboard=True)

        update.message.reply_text("Vincular a um pagamento existente?", reply_markup=reply_markup)
        return FIRST
    else:
        unknown = payee if exists(payer) else payer
        text = "A dívida não foi adicionada porque "+ unknown +" não está registrado(a) no orçamento."
        update.message.reply_text(text)

# vincula uma dívida a um pagamento
# COMPORTAMENTO: se uma pessoa X deve a Y, e ambos participam de um pagamento, vincular
# a dívida a ele faz X pagar a sua parte do pagamento E o que ele deve a Y, e Y paga sua
# parte subtraída do que lhe era devido.
def bindPayment(update: t.Update, context: tex.CallbackContext):
    if update.message.text == "Sim":
        pay_keys = []
        for p in payments:
            pay_keys.append( [p['name']] )
        reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

        update.message.reply_text("Selecione um pagamento.", reply_markup=reply_markup)
        return SECOND
    else:
        confirmDebt(update, context)

# Exibe uma mensagem de confirmação da criação de uma dívida
def confirmDebt(update: t.Update, context: tex.CallbackContext):
    latest = debts[-1]
    if update.message.text != "Não":
        latest['bound_payment'] = update.message.text
    text = "A dívida de "+latest['payer']+" a "+latest['payee']+" de valor R$"+str(latest['value'])+" foi adicionada"
    if latest['bound_payment'] != None:
        text += " e foi vinculada a "+latest['bound_payment']
    text += "."
    update.message.reply_text(text, reply_markup=t.ReplyKeyboardRemove())
    return END

# Exibe todos os pagamentos atuais
def showAllPays(update: t.Update, context: tex.CallbackContext):
    out = ""
    for i, p in enumerate(payments):
        out += str(i)+" "+p['name']+": "+p['value']+"\n"
    update.message.reply_text(out)

# Exibe todas as dívidas atuais
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
    dispatcher.add_handler(tex.CommandHandler('newperson', addPerson))
    dispatcher.add_handler(tex.CommandHandler('newpayment', addPay))
    debt_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('newdebt', addDebt)],
        states={
            FIRST: [tex.MessageHandler(tex.Filters.text, bindPayment)],
            SECOND: [tex.MessageHandler(tex.Filters.text, confirmDebt)]
        },
        fallbacks=[tex.CommandHandler('newdebt', addDebt)]
    )
    dispatcher.add_handler(debt_handler)
    dispatcher.add_handler(tex.CommandHandler('showpayments', showAllPays))
    dispatcher.add_handler(tex.CommandHandler('showdebts', showAllDebts))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

