import os
import re
import pytz
import telegram as t
import telegram.ext as tex
import logging as log
from dbhelper import DBHelper
from utils import toLower, purge, exists
from pymongo import errors
from datetime import datetime

ADD, SUB = range(1, 3)
database = None
os.environ['TZ'] = 'UTC'

token = os.environ['TOKEN']

# inicializa o bot
def start(update: t.Update, context: tex.CallbackContext):
    text = open("start.txt", "r").read()

    try:
        global database
        database = DBHelper(update.message.chat_id)
    except errors.ServerSelectionTimeoutError:
        text = "Ocorreu um erro ao abrir uma conexão com o servidor. Tente novamente. `Erro: serviço indisponível`"
    
    update.message.reply_markdown(text)

# adiciona uma pessoa no orçamento
def addPerson(update: t.Update, context: tex.CallbackContext):
    context.user_data['bot'] = update.message.reply_text("Você está adicionando uma nova pessoa. Entre com o seu nome de usuário. (ex: @gpupo)")
    return 1

def addPerson_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['handle'] = update.message.text
    #purge(update, context)

    context.user_data['bot'] = update.message.reply_text("Entre com um apelido dessa pessoa, que seja curto e fácil de lembrar. (ex: Pupo)")
    return 2

def addPerson_2(update: t.Update, context: tex.CallbackContext):
    #purge(update, context)

    person = { 'handle': context.user_data['handle'], 'alias': toLower(update.message.text) }
    database.commit('people', person)

    text = context.user_data['handle']+" foi adicionado(a)."
    update.message.reply_text(text)
    return tex.ConversationHandler.END

# adiciona um pagamento
def addPay(update: t.Update, context: tex.CallbackContext):
    context.user_data['bot'] = update.message.reply_text("Você está adicionando um novo pagamento. Entre com o nome do pagamento. (ex: Aluguel)")
    return 1

def addPay_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['name'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Entre com o valor do pagamento.")
    return 2

def addPay_2(update: t.Update, context: tex.CallbackContext):
    context.user_data['value'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Entre com as pessoas pagantes, separadas por vírgula.")
    return 3

def addPay_3(update: t.Update, context: tex.CallbackContext):
    payers = [toLower(person.strip()) for person in update.message.text.split(',')]
    population = database.dump('people')

    valid = True
    unknown = ""
    for p in payers:
        if not exists(p, population):
            valid = False
            unknown = p
            break
    if valid:
        value = [float(context.user_data['value'])/len(payers) for i in range(len(payers))]
        expenses = list(map(list, zip(payers, value)))

        payment = { 'name': context.user_data['name'], 'value': context.user_data['value'], 'expenses': expenses }
        database.commit('payments', payment)

        text = "O pagamento "+context.user_data['name']+" de valor R$"+'{0:.2f}'.format(float(context.user_data['value']))+" foi adicionado."
        update.message.reply_text(text)
    else:
        text = "O pagamento não foi adicionada porque "+ unknown +" não está registrado(a) no orçamento."
        update.message.reply_text(text)
    #purge(update, context)
    return tex.ConversationHandler.END

# adiciona uma dívida
def addDebt(update: t.Update, context: tex.CallbackContext):
    context.user_data['bot'] = update.message.reply_text("Você está adicionando uma nova dívida. Entre com o nome do devedor. Se houver múltiplos devedores, entre com o nome de cada um, separados por vírgula.")
    return 1

def addDebt_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['payer'] = [toLower(person.strip()) for person in update.message.text.split(',')]
    #purge(update, context)
    decision = [["0: Sim"], ["1: Não"]]
    reply_markup = t.ReplyKeyboardMarkup(decision, one_time_keyboard=True)
    context.user_data['bot'] = update.message.reply_text("Adicionar credor?", reply_markup=reply_markup)
    return 2

def addDebt_2(update: t.Update, context: tex.CallbackContext):
    decision = int(re.match(".+?(?=:)", update.message.text)[0])
    #purge(update, context)
    
    if decision == 0:
        context.user_data['bot'] = update.message.reply_text("Entre com o nome do credor.")
        return 3
    elif decision == 1:
        context.user_data['payee'] = None
        context.user_data['bot'] = update.message.reply_text("Entre com o valor devido.")
        return 4

def addDebt_3(update: t.Update, context: tex.CallbackContext):
    context.user_data['payee'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Entre com o valor devido.")
    return 4

def addDebt_4(update: t.Update, context: tex.CallbackContext):
    context.user_data['value'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Entre com uma descrição da dívida. (ex: Pedágio)")
    return 5

def addDebt_5(update: t.Update, context: tex.CallbackContext):
    payer = [toLower(p) for p in context.user_data['payer']]
    payee = toLower(context.user_data['payee']) if context.user_data['payee'] != None else None
    population = database.dump('people')

    payerValid = True
    unknown = None
    for p in payer:
        if not exists(p, population):
            payerValid = False
            unknown = p
            break

    if payerValid and (exists(payee, population) or payee == None):
        debt = { 'payer': payer, 'payee': payee, 'value': float(context.user_data['value']), 'description': update.message.text, 'bound': None }
        context.user_data['latest'] = debt
        payments = database.dump('payments')

        #purge(update, context)
        # vincula uma dívida a um pagamento
        # COMPORTAMENTO: se uma pessoa X deve a Y, e ambos participam de um pagamento, vincular
        # a dívida a ele faz X pagar a sua parte do pagamento E o que ele deve a Y, e Y paga sua
        # parte subtraída do que lhe era devido.

        pay_keys = []
        pay_keys.append( ["(não vincular)"] )
        for p in payments:
            pid, name = p['_id'], p['name']
            pay_keys.append( [f'{pid}: {name}'] )
        reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

        context.user_data['bot'] = update.message.reply_text("Selecione um pagamento para vincular à dívida.", reply_markup=reply_markup)
        return 6
    else:
        if unknown == None:
            unknown = payee
        text = "A dívida não foi adicionada porque "+ unknown +" não está registrado(a) no orçamento."
        update.message.reply_text(text)
        #purge(update, context)
    return tex.ConversationHandler.END

def updateExpenses(debt, reverse=False):
    value = debt['value']
    if reverse:
        value *= -1
    
    payment = database.find('payments', debt['bound'])
    expenses = payment['expenses']
    
    for p in debt['payer']:
        where = next(i for i, e in enumerate(expenses) if e[0] == p)
        expenses[where][1] += float(value)/len(debt['payer'])
    
    if debt['payee'] != None:
        where = next(i for i, e in enumerate(expenses) if e[0] == debt['payee'])
        expenses[where][1] -= float(value)

    database.update('payments', debt['bound'], {'expenses': expenses})
    return payment['name']

# Exibe uma mensagem de confirmação da criação de uma dívida
def confirmDebt(update: t.Update, context: tex.CallbackContext):
    debt = context.user_data['latest']
    
    if update.message.text != "(não vincular)":
        debt['bound'] = int(update.message.text.split(':')[0])
        bound_payment = updateExpenses(debt)
    text = "A dívida de"

    for p in debt['payer']:
        text += " "+p

    if debt['payee'] != None:
        text += " a "+debt['payee']
    
    text += " de valor R$"+'{0:.2f}'.format(float(debt['value']))+" foi adicionada"
    if debt['bound'] != None:
        text += " e foi vinculada a "+bound_payment
    text += "."
    
    update.message.reply_text(text, reply_markup=t.ReplyKeyboardRemove())
    database.commit('debts', debt)
    #purge(update, context)
    return tex.ConversationHandler.END

def updateExpenses_credit(credit, reverse=False):
    if reverse:
        credit['value'] *= -1
    
    payment = database.find('payments', credit['bound'])
    expenses = payment['expenses']
    
    where = next(i for i, e in enumerate(expenses) if e[0] == credit['person'])
    expenses[where][1] -= credit['value']

    database.update('payments', credit['bound'], {'expenses': expenses})
    return payment['name']

def addCredit(update: t.Update, context: tex.CallbackContext):
    context.user_data['bot'] = update.message.reply_text("Você está adicionando um novo crédito. Entre com o nome da pessoa a recebê-la.")
    return 1

def addCredit_1(update: t.Update, context: tex.CallbackContext):
    context.user_data['person'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Entre com o valor do crédito.")
    return 2

def addCredit_2(update: t.Update, context: tex.CallbackContext):
    context.user_data['value'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Entre com uma descrição para o crédito. (ex: Adiantou a sua parte do aluguel)")
    return 3

def addCredit_3(update: t.Update, context: tex.CallbackContext):
    population = database.dump('people')

    if exists(context.user_data['person'], population):
        credit = { 'person': toLower(context.user_data['person']), 'value': float(context.user_data['value']), 'description': update.message.text, 'bound': None }
        context.user_data['latest'] = credit
        payments = database.dump('payments')

        #purge(update, context)
        pay_keys = []
        pay_keys.append( ["(não vincular)"] )
        for p in payments:
            pid, name = p['_id'], p['name']
            pay_keys.append( [f'{pid}: {name}'] )
        reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

        context.user_data['bot'] = update.message.reply_text("Selecione um pagamento para vincular ao crédito.", reply_markup=reply_markup)
        return 4
    else:
        text = "O crédito não foi adicionado porque "+ context.user_data['person'] +" não está registrado(a) no orçamento."
        update.message.reply_text(text)
        #purge(update, context)
    return tex.ConversationHandler.END

def confirmCredit(update: t.Update, context: tex.CallbackContext):
    credit = context.user_data['latest']

    if update.message.text != "(não vincular)":
        credit['bound'] = int(update.message.text.split(':')[0])
        bound_payment = updateExpenses_credit(credit)
    text = "O crédito de "+credit['person']+" no valor R$"+'{0:.2f}'.format(float(credit['value']))+" foi adicionado"
    if credit['bound'] != None:
        text += " e foi vinculado a "+bound_payment
    text += "."
    update.message.reply_text(text, reply_markup=t.ReplyKeyboardRemove())
    database.commit('credits', credit)

    #purge(update, context)
    return tex.ConversationHandler.END

def showAllPeople(update: t.Update, context: tex.CallbackContext):
    out = ""
    people = database.dump('people')
    if len(people) == 0:
        out += "Não há pessoas registradas."
    else:
        for _, p in enumerate(people):
            out += str(p['_id'])+": "+p['handle']+" (ou "+p['alias']+")\n"
    update.message.reply_text(out)

def parsePayments():
    out = "<strong>Pagamentos registrados</strong>\n\n"
    payments = database.dump('payments')
    if len(payments) == 0:
        out += "Não há pagamentos registrados."
    else:
        for _, p in enumerate(payments):
            out += "<strong>"+p['name']+"</strong>\t\t\t"+'{0:.2f}'.format(float(p['value']))+"\n"
            for e in enumerate(p['expenses']):
                out += "\t\t\t\t\t\t\t\t"+str(e[1][0])+"\t\t\t\t\t"+'{0:.2f}'.format(float(e[1][1]))+"\n"
    return out

# Exibe todos os pagamentos atuais
def showAllPays(update: t.Update, context: tex.CallbackContext):
    update.message.reply_html(parsePayments())

def parseDebts():
    out = "<strong>Dívidas registradas</strong>\n\n"
    debts = database.dump('debts')
    if len(debts) == 0:
        out += "Não há dívidas registradas."
    else:
        for _, d in enumerate(debts):
            out += "<strong>"+d['description']+"</strong>\t\t\t"+'{0:.2f}'.format(float(d['value']))+"\n\t\t\t\t\t\t\t\t"
            for p in d['payer']:
                out += "<em>"+p+"</em> "
            
            if d['payee'] != None:
                out += "<strong>➪ "+d['payee']+"</strong>"

            out += "\n\n"
    return out

# Exibe todas as dívidas atuais
def showAllDebts(update: t.Update, context: tex.CallbackContext):
    update.message.reply_html(parseDebts())

def parseCredits():
    out = "<strong>Créditos registrados</strong>\n\n"
    credits = database.dump('credits')
    if len(credits) == 0:
        out += "Não há créditos registrados."
    else:
        for _, c in enumerate(credits):
            out += c['person']+"\t\t\t-"+'{0:.2f}'.format(float(c['value']))+" ("+c['description']+")\n"
    return out

def showAllCredits(update: t.Update, context: tex.CallbackContext):
    update.message.reply_html(parseCredits())

def showReport(update: t.Update, context: tex.CallbackContext):
    out = "<strong>Relatório completo de dívidas</strong>\n\n"
    out += parsePayments() + "\n" + parseDebts() + "\n" + parseCredits() + "\n"

    people = database.dump('people')
    payments = database.dump('payments')
    debts = database.dump('debts')
    credits = database.dump('credits')

    costs = [0] * len(people)
    out += "<strong>Valor total a pagar</strong>\n\n"
    for i, p in enumerate(people):
        for _, a in enumerate(payments):
            for _, e in enumerate(a['expenses']):                
                if e[0] == p['alias']:
                    costs[i] += e[1]
        
        for _, d in enumerate(debts):
            if d['bound'] == None:
                if p['alias'] in d['payer']:
                    costs[i] += d['value']/len(d['payer'])
        
        for _, c in enumerate(credits):
            if c['bound'] == None:
                if p['alias'] == c['person']:
                    costs[i] -= c['value']
        
        out += people[i]['handle']+": "+'{0:.2f}'.format(float(costs[i]))+"\n"
    update.message.reply_html(out)

def setReminder_selector(update: t.Update, context: tex.CallbackContext):
    pay_keys = []
    payments = database.dump('payments')
    for _, p in enumerate(payments):
        pay_keys.append( [str(p['_id'])+": "+p['name']] )
    reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

    context.user_data['bot'] = update.message.reply_text("Selecione um pagamento.", reply_markup=reply_markup)
    return 1

def setReminder_date(update: t.Update, context: tex.CallbackContext):
    context.user_data['payment'] = update.message.text
    #purge(update, context)
    context.user_data['bot'] = update.message.reply_text("Defina a data do lembrete. (dd/mm/aaaa)")
    return 2

def reminderCallback(context: tex.CallbackContext):
    chatID, paymentName = context.job.context
    text = 'Lembrete! O pagamento '+paymentName+' precisa ser pago em alguns dias.'
    context.bot.send_message(chat_id=chatID, text=text)

def setReminder(update: t.Update, context: tex.CallbackContext):
    date = [int(d) for d in update.message.text.strip().split('/')]
    payment = context.user_data['payment'].split(':')[-1].strip()
    
    when = datetime(date[2], date[1], date[0], 16, 5, 0, tzinfo=pytz.utc)

    context.job_queue.run_once(reminderCallback, when, context=[update.message.chat_id, payment])
    #purge(update, context)
    update.message.reply_text('Lembrete marcado para '+str(date[0])+'/'+str(date[1])+'/'+str(date[2]))

    
def deletePerson_selector(update: t.Update, context: tex.CallbackContext):
    person_keys = []
    people = database.dump('people')

    for _, p in enumerate(people):
        person_keys.append( [str(p['_id'])+": "+p['handle']] )
    reply_markup = t.ReplyKeyboardMarkup(person_keys, one_time_keyboard=True)

    context.user_data['bot'] = update.message.reply_text("Selecione uma pessoa.", reply_markup=reply_markup)

    return 1

def deletePerson(update: t.Update, context: tex.CallbackContext):
    id = int(update.message.text.split(':')[0])
    person = database.find('people', id)

    payments = database.dump('payments')
    people = database.dump('people')
    debts = database.dump('debts')
    credits = database.dump('credits')

    for i, p in enumerate(payments):
        for _, e in enumerate(p['expenses']):
            if e[0] == person['alias']:
                # del payments[i]
                database.delete('payments', p['_id'])
                continue
    for i, d in enumerate(debts):
        if person['alias'] in d['payer'] or person['alias'] == d['payee']:
            # del debts[i]
            database.delete('debts', d['_id'])
            continue
    for i, c in enumerate(credits):
        if person['alias'] == c['person']:
            # del credits[i]
            database.delete('credits', c['_id'])
            continue

    text = person['handle'] + " foi removido(a), assim como todos os pagamentos, dívidas e créditos em seu nome."
    # del people[where]
    database.delete('people', id)
    update.message.reply_text(text)
    #purge(update, context)
    return tex.ConversationHandler.END

def deletePay_selector(update: t.Update, context: tex.CallbackContext):
    pay_keys = []
    payments = database.dump('payments')
    for _, p in enumerate(payments):
        pay_keys.append( [str(p['_id'])+": "+p['name']] )
    reply_markup = t.ReplyKeyboardMarkup(pay_keys, one_time_keyboard=True)

    context.user_data['bot'] = update.message.reply_text("Selecione um pagamento.", reply_markup=reply_markup)
    return 2

def deletePay(update: t.Update, context: tex.CallbackContext):
    id = int(update.message.text.split(':')[0])
    payment = database.find('payments', id)
    debts = database.dump('debts')
    credits = database.dump('credits')

    print(payment)

    for i, d in enumerate(debts):
        if d['bound'] == payment['_id']:
            # del debts[i]
            database.delete('debts', d['_id'])
    for i, c in enumerate(credits):
        if c['bound'] == payment['_id']:
            # del credits[i]
            database.delete('credits', c['_id'])
    text = "O pagamento "+payment['name']+" foi removido, assim como todas as suas dívidas e seus créditos vinculados."
    #del payments[where]
    database.delete('payments', id)
    update.message.reply_text(text)
    #purge(update, context)
    return tex.ConversationHandler.END

def deleteDebt_selector(update: t.Update, context: tex.CallbackContext):
    debt_keys = []
    debts = database.dump('debts')
    for _, d in enumerate(debts):
        debt_keys.append( [str(d['_id'])+": "+d['description']] )
    reply_markup = t.ReplyKeyboardMarkup(debt_keys, one_time_keyboard=True)

    context.user_data['bot'] = update.message.reply_text("Selecione uma dívida.", reply_markup=reply_markup)
    return 3

def deleteDebt(update: t.Update, context: tex.CallbackContext):
    id = int(update.message.text.split(':')[0])
    debt = database.find('debts', id)

    text = "A dívida de"
    for p in debt['payer']:
        text += " "+p

    if debt['payee'] != None:
        text += " a "+debt['payee']
    text += " de valor R$"+'{0:.2f}'.format(float(debt['value']))+" foi removida."

    if debt['bound'] != None:
        updateExpenses(debt, True)
    # del debts[where]
    database.delete('debts', debt['_id'])

    update.message.reply_text(text)
    #purge(update, context)
    return tex.ConversationHandler.END

def deleteCredit_selector(update: t.Update, context: tex.CallbackContext):
    credit_keys = []
    credits = database.dump('credits')
    for _, c in enumerate(credits):
        credit_keys.append( [str(c['_id'])+": crédito de "+c['person']+" no valor "+'{0:.2f}'.format(float(c['value']))] )
    reply_markup = t.ReplyKeyboardMarkup(credit_keys, one_time_keyboard=True)

    context.user_data['bot'] = update.message.reply_text("Selecione um crédito.", reply_markup=reply_markup)
    return 1

def deleteCredit(update: t.Update, context: tex.CallbackContext):
    id = int(update.message.text.split(':')[0])
    credit = database.find('credits', id)

    text = "O crédito de "+credit['person']+" no valor R$"+'{0:.2f}'.format(float(credit['value']))+" foi removido."
    if credit['bound'] != None:
        updateExpenses_credit(credit, True)
    # del credits[where]
    database.delete('credits', credit['_id'])
    update.message.reply_text(text)
    #purge(update, context)
    return tex.ConversationHandler.END

def main():
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
    dispatcher.add_handler(tex.CommandHandler('showreport', showReport))

    reminder_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('setreminder', setReminder_selector)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, setReminder_date)],
            2: [tex.MessageHandler(tex.Filters.text, setReminder, pass_job_queue=True)]
        },
        fallbacks=[tex.CommandHandler('setreminder', setReminder_selector)]
    )
    dispatcher.add_handler(reminder_handler)

    delete_person_handler = tex.ConversationHandler(
        entry_points=[tex.CommandHandler('deleteperson', deletePerson_selector)],
        states={
            1: [tex.MessageHandler(tex.Filters.text, deletePerson)]
        },
        fallbacks=[tex.CommandHandler('deleteperson', deletePerson_selector)]
    )
    dispatcher.add_handler(delete_person_handler)

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

    updater.start_webhook(listen="0.0.0.0", port=int(os.environ.get('PORT', '8443')), url_path=token)
    updater.bot.set_webhook('https://tesourobot.herokuapp.com/'+token)
    # updater.start_polling()
    # updater.idle()

if __name__ == "__main__":
    main()

