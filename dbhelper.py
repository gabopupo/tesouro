from pymongo import MongoClient
from secrets import mongourl

class DBHelper:
    def __init__(self, chat_id):
        self.chat_id = str(chat_id)
        self.client = MongoClient(mongourl)
        self.my_base = self.client[self.chat_id]

        if self.my_base['counters'].count_documents({}) == 0:
            self.my_base['counters'].insert_one({ '_id': 'people', 'seq': 0 })
            self.my_base['counters'].insert_one({ '_id': 'payments', 'seq': 0 })
            self.my_base['counters'].insert_one({ '_id': 'debts', 'seq': 0 })
            self.my_base['counters'].insert_one({ '_id': 'credits', 'seq': 0 })

    def __autoinc(self, collection):
        ret = self.my_base.counters.find_one_and_update(
            { '_id': collection }, { '$inc': { 'seq': 1 } }    
        )
        return ret['seq']

    def __autodec(self, collection):
        self.my_base.counters.find_one_and_update(
            { '_id': collection }, { '$inc': { 'seq': -1 } }
        )

    def commit(self, collection, data):
        data.update({'_id': self.__autoinc(collection)})
        self.my_base[collection].insert_one(data)

    def find(self, collection, data_id):
        return self.my_base[collection].find_one({'_id': data_id})

    def dump(self, collection):
        return self.my_base[collection].find({})

    def update(self, collection, queryID, newData):
        self.my_base[collection].update_one({'_id': queryID}, {'$set': newData}, upsert=False)

    def delete(self, collection, queryID):
        self.__autodec(collection)
        self.my_base[collection].delete_one({'_id': queryID})