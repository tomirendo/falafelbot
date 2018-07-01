#!/usr/bin/python3
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler
import telegram
import sched
import threading
import time
from random import choice

with open("key.txt") as f:
    key = f.read().strip()

MINIMUM_FOR_ORDER = 4
TWENTY_MINUTES_IN_SECONDS = 60 * 20
FIFTEEN_MINUTES_IN_SECONDS = 60 * 15

s = sched.scheduler()

welcome_message = """
שלום כפרה, זה הפלאפלר

כדי להזמין פלאפל (או סביך) שולחים 
/falafel
כדי לבדוק מה המצב של ההזמנה שולחים 
/status
כדי לבטל את ההזמנה שלך, שולחים
/remove

אחרי שההזמנה מתחילה אני מחכה 20 דק׳
אם יש מספיק ({}) מזמינים אני מגריל אחראי משלוח והוא צריך להתקשר
אם אין מספיק, ההזמנה מבוטלת. סורי נשמה, לא התכוונתי, אין מה לעשות.

""".format(MINIMUM_FOR_ORDER)

orderrer_text = '''
מזל טוב מותק, את צריכה להתקשר לשבח

מספר הטלפון הוא:
02-6528317
תזמיני את השליח לאקווריום, כי אנחנו בכל זאת חיים בחברה.

כשהאוכל מגיע, תשלחי /done ואני אודיע לכולם לבוא

טוב סורי על החפירה, הנה ההזמנות:
'''


what_would_you_like_message_1 = """מה לשים לך בפיתה, בובה? (או לאפה אבל ראבק תגידי)"""

import json
class Chats:
    def __init__(self, filename = 'chats.json'):
        self.filename = filename
        try :
            with open(self.filename) as f:
                self.all_chats = json.loads(f.read())
        except :
            self.all_chats = []
        
    def get_all_chats(self):
        return self.all_chats 

    def add_chat(self, chat_id): 
        if chat_id not in self.all_chats:
            self.all_chats.append(chat_id)
            with open(self.filename,"w") as f:
                f.write(json.dumps(self.all_chats))


from collections import namedtuple
class Order:
    def __init__(self, contact, text, chat_id):
        self.contact = contact
        self.text = text
        self.chat_id = chat_id
        self.payment_method = ""
        
Orderer = namedtuple("Orderer","contact, chat_id")

class OrderManager:
    def __init__(self):
        self.open = False
        self.running_orders = []
        self.orders = []
        self.orderrer = None
    
    def begin_order(self, chat_id, contact):
        order = self.get_running_order_by_chat_id(chat_id)
        if order is not None:
            self.running_orders.remove(order)
        order = Order(contact = contact,chat_id=chat_id ,text = "")
        self.running_orders.append(order)
        
    def get_running_order_by_chat_id(self, chat_id):
        for i in self.running_orders:
            if i.chat_id == chat_id:
                return i
            
    def is_waiting_for_text(self, chat_id):
        order = self.get_running_order_by_chat_id(chat_id)
        return not bool(order.text)
    
    def is_running_order(self, chat_id):
        if self.get_running_order_by_chat_id(chat_id) is None:
            return False
        return True
        
    def update_order_with_text(self, chat_id, text):
        order = self.get_running_order_by_chat_id(chat_id)
        order.text = text
    
    def update_order_with_payment(self, chat_id, payment):
        order = self.get_running_order_by_chat_id(chat_id)
        order.payment = payment
        self.running_orders.remove(order)
        self.orders.append(order)
        if len(self.orders) == 1:
            return True
    def get_order(self, chat_id):
        for i in self.orders:
            if i.chat_id == chat_id:
                return i

    def remove_order(self, chat_id):
        a = self.get_order(chat_id)
        if a is not None:
            self.orders.remove(a)
       
    def open_order(self):
        self.close_order()
        self.open = True 

    def close_order(self):
        self.open = False
        self.orders = []
        self.orderrer = None

    def did_order(self, chat_id):
        return self.get_order(chat_id) is not None

    def is_final(self):
        return self.orderrer is not None

    def order_is_big_enough(self):
        return len(self.orders) >= MINIMUM_FOR_ORDER

    def cancel(self, bot):
        for i in self.orders:
            i.contact.send_message(text = 'לא היו מספיק אנשים ואני מבטל את ההזמנה. סורי כפרות')
        self.close_order()

    def finalize(self, bot, orderrer = None):
        if orderrer is not None:
            self.orderrer = orderrer
        else : 
            self.orderrer = choice([i.contact for i in self.orders])
        self.orderrer.send_message(text = orderrer_text)
        self.orderrer.send_message(text = self.orders_description(), parse_mode = telegram.ParseMode.HTML)
        for order in self.orders:
            if order.contact != self.orderrer:
                order.contact.send_message(text = '{} נבחרה להתקשר, מזומנות להציק לה אם ממשהו לא בסדר. ויקירה את תקבלי הודעה כשהאוכל יגיע אז אין מה לדאוג'.format(self.orderrer.mention_html()), parse_mode = telegram.ParseMode.HTML)
            
        
    def done(self, bot):
        for order in self.orders:
            if order.contact != self.orderrer:
                order.contact.send_message(text = 'היי האוכל הגיע ומחכה לך באקווריום. צאי מהמחשב שניה יא חנונית')
        self.orderrer.send_message(text = 'כפרה עליך, הודעתי לכולם והם באים. בתאבון!')
        self.open_order()
	
        
    def alert_before_final(self, bot):
        if len(self.orders) >= MINIMUM_FOR_ORDER:
            message = 'אל דאגה, יש {} מזמינים ועוד חמש דקות אני בוחר פראייר שמתקשר לשבח'.format(len(self.orders))
        else :
            message = 'מאמי, עוד 5 דק׳ צריך להתקשר ואין מספיק מזמינים. אם אף אחד לא יצוץ אני מבטל ת׳הזמנה'
        for order in self.orders:
            bot.send_message(chat_id = order.chat_id, 
				text = message)
            
    
    def orders_description(self):
        number = len(self.orders)
        txt = "מספר המזמינים {}".format(number) + "\n"
        for order in self.orders:
            txt += "{1} - {0} - {2} \n".format(order.contact.mention_html(),order.contact.full_name, order.text)
        return txt
        

current_order = OrderManager()
chats = Chats()
def start(bot, update):
    print('Got a start')
    chats.add_chat(update.message.chat_id)
    bot.send_message(chat_id = update.message.chat_id,
                    text =  welcome_message)
    print(chats.get_all_chats())
    
def add(bot, update):
    try : 
        if current_order.is_final():
            bot.send_message(chat_id = update.message.chat_id,
 				text = 'סורי מאמי בדיוק יצאה הזמנה. חכי עוד כמה דקות ואני איתך')
        elif current_order.did_order(update.message.chat_id):
            bot.send_message(chat_id = update.message.chat_id, 
				text = '''
מאמי את כבר נמצאת בהזמנה. כדי לשנות משהו תבטלי עם
/remove
ותתחילי מחדש
				''')
        else :
            current_order.begin_order(update.message.chat_id, update.message.from_user)
            bot.send_message(chat_id = update.message.chat_id,  text = what_would_you_like_message_1)
    except Exception as e: 
        print(e) 

def notify(bot, chat_id):
    print("Notify Everyone")
    for chat in chats.get_all_chats():
            if chat != chat_id:
                bot.send_message(chat_id= chat,
             text = """מישהו מזמין פלאפל. זה הזמן להזמין פלאפל. פלאפל. (תלחץ /falafel )""")
 
def text(bot, update):
    try:
        text = update.message.text 
        chat_id = update.message.chat_id
        print(text, chat_id)
        if text.startswith('תודה') :
            
            bot.send_message(chat_id = update.message.chat_id,
				text = 'מה תודה?')

            bot.send_message(chat_id = update.message.chat_id,
				text = 'תתפשטי')
            time.sleep(3)
            bot.send_message(chat_id = update.message.chat_id,
				text = 'חחחחחחחח סתם סתם את יודעת שאני מת עליך')

            return 

        if current_order.get_running_order_by_chat_id(chat_id) is None:
            bot.send_message(chat_id = update.message.chat_id,
				text = 'אחותי נשבע שלא הבנתי כלום\n אם את צריכה הסברים תלחצי\n /start')
            return 
        
        if current_order.is_waiting_for_text(chat_id):
            print("Got Here")
            current_order.update_order_with_text(chat_id, text)
            
            
            kb = telegram.ReplyKeyboardMarkup([["מזומן","פפר","Paybox"]])
            bot.send_message(chat_id = chat_id,
                            text = "איך תשלמי?",
                            reply_markup = kb)
        elif current_order.is_running_order(chat_id):
            is_first_order = current_order.update_order_with_payment(chat_id, text)
            bot.send_message(chat_id = chat_id,
                            text = 'קלאס, ההזמנה נוספה. ', reply_markup=telegram.replykeyboardremove.ReplyKeyboardRemove())
            if is_first_order:
                def f():
                    s.enter(FIFTEEN_MINUTES_IN_SECONDS, 1, alert_before_final,argument=(bot,))
                    s.enter(TWENTY_MINUTES_IN_SECONDS, 1,wait_is_over,argument=(bot,))
                    s.run()
                t = threading.Thread(target = f)
                t.start()
                notify(bot, chat_id)
            
    except Exception as e:
        print(e)

def alert_before_final(bot):
    print("Alert before order is final")
    current_order.alert_before_final(bot)
    
def wait_is_over(bot):
    print("Wait is over")
    if current_order.order_is_big_enough():
        current_order.finalize(bot)
    else : 
        current_order.cancel(bot)

def done (bot, update):
    if current_order.orderrer is None :
        update.message.from_user.send_message(text = 'בלי שטויות בובה')
        return
    if update.message.chat_id == current_order.orderrer.id:
        current_order.done(bot)
    
def status(bot, update):
    bot.send_message(chat_id = update.message.chat_id,
                     text = current_order.orders_description(),
                     parse_mode = telegram.ParseMode.HTML)
def remove(bot, update):
    try:
        if current_order.is_final():
            bot.send_message(chat_id = update.message.chat_id,
			text = 'אני מצטער אבל ההזמנה יצאה כבר, אי אפשר לבטל')
        else: 
            current_order.remove_order(update.message.chat_id)
            bot.send_message(chat_id = update.message.chat_id,
			text = 'צודקת, על גוף כמו שלך צריך לשמור. ההזמנה בוטלה')
    except Exception as e:
        print(e)
    
    
def notify_all(bot, update):
    with open("notification.txt","rb") as f:
        message = f.read().decode()
    for chat_id in chats.get_all_chats():
        bot.send_message(chat_id = chat_id,
			text = message)
 
updater = Updater(token = key)
dispatcher = updater.dispatcher
start_handler = CommandHandler('start', start)
add_handler = CommandHandler('falafel', add)
status_handler = CommandHandler('status', status)
remove_handler = CommandHandler('remove', remove)
done_handler= CommandHandler('done', done)
text_handler = MessageHandler(Filters.text, text)
dispatcher.add_handler(text_handler)
dispatcher.add_handler(remove_handler)
dispatcher.add_handler(done_handler)
dispatcher.add_handler(status_handler)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(add_handler)
updater.start_polling()
    
