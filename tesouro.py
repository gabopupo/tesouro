from decimal import getcontext, Decimal
import re
import telegram as t
import telegram.ext as tex
import logging as log
import uuid

ADD, SUB = range(1, 3)
people = []
payments = []
debts = []
credits = []

# inicializa o bot
def start(update: t.Update, context: tex.CallbackContext):
    text = open("start.txt", "r").read()
    update.message.reply_text(text)

def toLower(s):
    s = str(s)
    return s.lower()

# adiciona uma pessoa no orçamento
def addPerson(update: t.Update, context: tex.CallbackContext):
    update.message.reply_text("Você está adicionando uma nova pessoa. Entre com o seu nome de usuário. (ex: @gpupo)")
    return 1

def addPerson_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['handle'] = update.message.text
    update.message.reply_text("Entre com um apelido dessa pessoa, que seja curto e fácil de lembrar. (ex: Pupo)")
    return 2

def addPerson_2(update: t.Update, context: tex.CallbackContext):
    people.append({ 'id': uuid.uuid4(), 'handle': context.user_data['handle'], 'alias': toLower(update.message.text) })
    text = context.user_data['handle']+" foi adicionado(a)."
    update.message.reply_text(text)
    return tex.ConversationHandler.END
    
def exists(person):
    return (any(person == p['alias'] for p in people) or any(person == p['handle'] for p in people))

# adiciona um pagamento
def addPay(update: t.Update, context: tex.CallbackContext):
    update.message.reply_text("Você está adicionando um novo pagamento. Entre com o nome do pagamento. (ex: Aluguel)")
    return 1

def addPay_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['name'] = update.message.text
    update.message.reply_text("Entre com o valor do pagamento.")
    return 2

def addPay_2(update: t.Update, context: tex.CallbackContext):
    context.user_data['value'] = update.message.text
    update.message.reply_text("Entre com as pessoas pagantes, separadas por vírgula.")
    return 3

def addPay_3(update: t.Update, context: tex.CallbackContext):
    payers = [toLower(person.strip()) for person in update.message.text.split(',')]
    valid = True
    unknown = ""
    for p in payers:
        if not exists(p):
            valid = False
            unknown = p
            break
    if valid:
        value = [Decimal(context.user_data['value'])/len(payers) for i in range(len(payers))]
        expenses = list(map(list, zip(payers, value)))

        payments.append( { 'id': uuid.uuid4(), 'name': context.user_data['name'], 'value': context.user_data['value'], 'expenses': expenses })
        text = "O pagamento "+context.user_data['name']+" de valor R$"+str(context.user_data['value'])+" foi adicionado."
        update.message.reply_text(text)
    else:
        text = "A dívida não foi adicionada porque "+ unknown +" não está registrado(a) no orçamento."
        update.message.reply_text(text)
    return tex.ConversationHandler.END

# adiciona uma dívida
def addDebt(update: t.Update, context: tex.CallbackContext):
    update.message.reply_text("Você está adicionando uma nova dívida. Entre com o nome do devedor.")
    return 1

def addDebt_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['payer'] = update.message.text
    decision = [["0: Adicionar credor"], ["1: Compensar em um pagamento"]]
    reply_markup = t.ReplyKeyboardMarkup(decision, one_time_keyboard=True)
    update.message.reply_text("O que deseja fazer?", reply_markup=reply_markup)
    return 2

def addDebt_2(update: t.Update, context: tex.CallbackContext):
    decision = int(re.match(".+?(?=:)", update.message.text)[0])
    
    if decision == 0:
        update.message.reply_text("Entre com o nome do credor.")
        return 3
    elif decision == 1:
        context.user_data['payee'] = None
        update.message.reply_text("Entre com o valor devido.")
        return 4

def addDebt_3(update: t.Update, context: tex.CallbackContext):
    context.user_data['payee'] = update.message.text
    update.message.reply_text("Entre com o valor devido.")
    return 4

def addDebt_4(update: t.Update, context: tex.CallbackContext):
    context.user_data['value'] = update.message.text
    update.message.reply_text("Entre com uma descrição da dívida. (ex: Pedágio)")
    return 5

def addDebt_5(update: t.Update, context: tex.CallbackContext):
    payer, payee = toLower(context.user_data['payer']), toLower(context.user_data['payee']) if context.user_data['payee'] != None else None
    if exists(payer) and (exists(payee) or payee == None):
        debts.append({ 'id': uuid.uuid4(), 'payer': payer, 'payee': payee, 'value': Decimal(context.user_data['value']), 'description': update.message.text, 'bound': None })
    
        # vincula uma dívida a um pagamento
        # COMPORTAMENTO: se uma pessoa X deve a Y, e ambos participam de um pagamento, vincular
        # a dívida a ele faz X pagar a sua parte do pagamento E o que ele deve a Y, e Y paga sua
        # parte subtraída do que lhe era devido.

        pay_keys = []
        pay_keys.append( ["(não vincular)"] )
        for p in payments:
            pay_keys.append( [p['name']] )
        reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

        update.message.reply_text("Selecione um pagamento para vincular à dívida.", reply_markup=reply_markup)
        return 6
    else:
        unknown = payee if exists(payer) else payer
        text = "A dívida não foi adicionada porque "+ unknown +" não está registrado(a) no orçamento."
        update.message.reply_text(text)

def updateExpenses(debt, reverse=False):
    if reverse:
        debt['value'] *= -1
    
    where = next(i for i, p in enumerate(payments) if p['name'] == debt['bound'])
    expenses = payments[where]['expenses']
    
    where = next(i for i, e in enumerate(expenses) if e[0] == debt['payer'])
    expenses[where][1] += debt['value']
    
    if debt['payee'] != None:
        where = next(i for i, e in enumerate(expenses) if e[0] == debt['payee'])
        expenses[where][1] -= debt['value']

# Exibe uma mensagem de confirmação da criação de uma dívida
def confirmDebt(update: t.Update, context: tex.CallbackContext):
    latest = debts[-1]
    if update.message.text != "(não vincular)":
        latest['bound'] = update.message.text
        updateExpenses(latest)
    text = "A dívida de "+latest['payer']
    if latest['payee'] != None:
        text += " a "+latest['payee']
    text += " de valor R$"+str(latest['value'])+" foi adicionada"
    if latest['bound'] != None:
        text += " e foi vinculada a "+latest['bound']
    text += "."
    update.message.reply_text(text, reply_markup=t.ReplyKeyboardRemove())
    return tex.ConversationHandler.END

def updateExpenses_credit(credit, reverse=False):
    if reverse:
        credit['value'] *= -1
    
    where = next(i for i, p in enumerate(payments) if p['name'] == credit['bound'])
    expenses = payments[where]['expenses']
    
    where = next(i for i, e in enumerate(expenses) if e[0] == credit['person'])
    expenses[where][1] -= credit['value']

def addCredit(update: t.Update, context: tex.CallbackContext):
    update.message.reply_text("Você está adicionando um novo crédito. Entre com o nome da pessoa a recebê-la.")
    return 1

def addCredit_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['person'] = update.message.text
    update.message.reply_text("Entre com o valor do crédito.")
    return 2

def addCredit_2(update: t.Update, context: tex.CallbackContext):
    context.user_data['value'] = update.message.text
    update.message.reply_text("Entre com uma descrição para o crédito. (ex: Adiantou a sua parte do aluguel)")
    return 3

def addCredit_3(update: t.Update, context: tex.CallbackContext):
    if exists(context.user_data['person']):
        credits.append({ 'id': uuid.uuid4(), 'person': toLower(context.user_data['person']), 'value': Decimal(context.user_data['value']), 'description': update.message.text, 'bound': None })
        
        pay_keys = []
        pay_keys.append( ["(não vincular)"] )
        for p in payments:
            pay_keys.append( [p['name']] )
        reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

        update.message.reply_text("Selecione um pagamento para vincular ao crédito.", reply_markup=reply_markup)
        return 4
    else:
        text = "O crédito não foi adicionado porque "+ context.user_data['person'] +" não está registrado(a) no orçamento."
        update.message.reply_text(text)

def confirmCredit(update: t.Update, context: tex.CallbackContext):
    latest = credits[-1]
    if update.message.text != "(não vincular)":
        latest['bound'] = update.message.text
        updateExpenses_credit(latest)
    text = "O crédito de "+latest['person']+" no valor R$"+str(latest['value'])+" foi adicionado"
    if latest['bound'] != None:
        text += " e foi vinculado a "+latest['bound']
    text += "."
    update.message.reply_text(text, reply_markup=t.ReplyKeyboardRemove())
    return tex.ConversationHandler.END

def showAllPeople(update: t.Update, context: tex.CallbackContext):
    out = ""
    if len(people) == 0:
        out += "Não há pessoas registradas."
    else:
        for i, p in enumerate(people):
            out += p['handle']+" (ou "+p['alias']+")\n"
    update.message.reply_text(out)

# Exibe todos os pagamentos atuais
def showAllPays(update: t.Update, context: tex.CallbackContext):
    out = ""
    if len(payments) == 0:
        out += "Não há pagamentos registrados."
    else:
        for i, p in enumerate(payments):
            out += p['name']+": "+p['value']+"\n"
            for e in enumerate(p['expenses']):
                out += "\t\t\t"+str(e[1][0])+"\t\t"+str(e[1][1])+"\n"
    update.message.reply_text(out)

# Exibe todas as dívidas atuais
def showAllDebts(update: t.Update, context: tex.CallbackContext):
    out = ""
    if len(debts) == 0:
        out += "Não há dívidas registradas."
    else:
        for i, d in enumerate(debts):
            out += d['payer']
            if d['payee'] != None:
                out += " -> "+d['payee']
            out += ": "+str(d['value'])+"\t("+d['description']+")\n"
    update.message.reply_text(out)

def showAllCredits(update: t.Update, context: tex.CallbackContext):
    out = ""
    if len(credits) == 0:
        out += "Não há créditos registrados."
    else:
        for i, c in enumerate(credits):
            out += c['person']+"\t\t-"+str(c['value'])+" ("+c['description']+")\n"
    update.message.reply_text(out)

def deletePay_selector(update: t.Update, context: tex.CallbackContext):
    pay_keys = []
    for i, p in enumerate(payments):
        pay_keys.append( [str(i)+": "+p['name']] )
    reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

    update.message.reply_text("Selecione um pagamento.", reply_markup=reply_markup)

    return 2

def deletePay(update: t.Update, context: tex.CallbackContext):
    where = int(re.match(".+?(?=:)", update.message.text)[0])
    for i, d in enumerate(debts):
        if d['bound'] == payments[where]['name']:
            del debts[i]
    for i, c in enumerate(credits):
        if c['bound'] == payments[where]['name']:
            del credits[i]
    text = "O pagamento "+payments[where]['name']+" foi removido, assim como todas as suas dívidas e seus créditos vinculados."
    del payments[where]
    update.message.reply_text(text)
    return tex.ConversationHandler.END

def deleteDebt_selector(update: t.Update, context: tex.CallbackContext):
    debt_keys = []
    for i, d in enumerate(debts):
        debt_keys.append( [str(i)+": "+d['description']] )
    reply_markup = t.ReplyKeyboardMarkup(debt_keys, one_time_keyboard=True)

    update.message.reply_text("Selecione uma dívida.", reply_markup=reply_markup)
    
    return 3

def deleteDebt(update: t.Update, context: tex.CallbackContext):
    where = int(re.match(".+?(?=:)", update.message.text)[0])
    text = "A dívida de "+debts[where]['payer']
    if debts[where]['payee'] != None:
        text += " a "+debts[where]['payee']
    text += " de valor R$"+str(debts[where]['value'])+" foi removida."
    if debts[where]['bound'] != None:
        updateExpenses(debts[where], True)
    del debts[where]
    update.message.reply_text(text)
    return tex.ConversationHandler.END

def deleteCredit_selector(update: t.Update, context: tex.CallbackContext):
    credit_keys = []
    for i, c in enumerate(credits):
        credit_keys.append( [str(i)+": crédito de "+c['person']+" no valor "+str(c['value'])] )
    reply_markup = t.ReplyKeyboardMarkup(credit_keys, one_time_keyboard=True)

    update.message.reply_text("Selecione um crédito.", reply_markup=reply_markup)
    
    return 1

def deleteCredit(update: t.Update, context: tex.CallbackContext):
    where = int(re.match(".+?(?=:)", update.message.text)[0])
    text = "O crédito de "+credits[where]['person']+" no valor R$"+str(credits[where]['value'])+" foi removido."
    if credits[where]['bound'] != None:
        updateExpenses_credit(credits[where], True)
    del credits[where]
    update.message.reply_text(text)
    return tex.ConversationHandler.END

def main():
    getcontext().prec = 2
    updater = tex.Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    log.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=log.INFO)

    dispatcher.add_handler(tex.CommandHandler('start', start))

    person_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('newperson', addPerson)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, addPerson_1)],
            2: [tex.MessageHandler(tex.Filters.text, addPerson_2)]
        },
        fallbacks=[tex.CommandHandler('newperson', addPerson)]
    )
    dispatcher.add_handler(person_handler)

    payment_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('newpayment', addPay)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, addPay_1)],
            2: [tex.MessageHandler(tex.Filters.text, addPay_2)],
            3: [tex.MessageHandler(tex.Filters.text, addPay_3)]
        },
        fallbacks=[tex.CommandHandler('newpayment', addPay)]
    )
    dispatcher.add_handler(payment_handler)

    debt_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('newdebt', addDebt)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, addDebt_1)],
            2: [tex.MessageHandler(tex.Filters.text, addDebt_2)],
            3: [tex.MessageHandler(tex.Filters.text, addDebt_3)],
            4: [tex.MessageHandler(tex.Filters.text, addDebt_4)],
            5: [tex.MessageHandler(tex.Filters.text, addDebt_5)],
            6: [tex.MessageHandler(tex.Filters.text, confirmDebt)]
        },
        fallbacks=[tex.CommandHandler('newdebt', addDebt)]
    )
    dispatcher.add_handler(debt_handler)

    credit_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('newcredit', addCredit)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, addCredit_1)],
            2: [tex.MessageHandler(tex.Filters.text, addCredit_2)],
            3: [tex.MessageHandler(tex.Filters.text, addCredit_3)],
            4: [tex.MessageHandler(tex.Filters.text, confirmCredit)]
        },
        fallbacks=[tex.CommandHandler('newcredit', addCredit)]
    )
    dispatcher.add_handler(credit_handler)

    dispatcher.add_handler(tex.CommandHandler('showpeople', showAllPeople))
    dispatcher.add_handler(tex.CommandHandler('showpayments', showAllPays))
    dispatcher.add_handler(tex.CommandHandler('showdebts', showAllDebts))
    dispatcher.add_handler(tex.CommandHandler('showcredits', showAllCredits))
    delete_pay_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('deletepayment', deletePay_selector)],
        states={
            2: [tex.MessageHandler(tex.Filters.text, deletePay)]
        },
        fallbacks=[tex.CommandHandler('deletepayment', deletePay_selector)]
    )
    dispatcher.add_handler(delete_pay_handler)

    delete_debt_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('deletedebt', deleteDebt_selector)],
        states={
            3: [tex.MessageHandler(tex.Filters.text, deleteDebt)]
        },
        fallbacks=[tex.CommandHandler('deletecredit', deleteDebt_selector)]
    )
    dispatcher.add_handler(delete_debt_handler)

    delete_credit_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('deletecredit', deleteCredit_selector)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, deleteCredit)]
        },
        fallbacks=[tex.CommandHandler('deletecredit', deleteCredit_selector)]
    )
    dispatcher.add_handler(delete_credit_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

