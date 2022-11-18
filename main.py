from dataclasses import field
import traceback
import os
import re
import datetime
import urllib
import unittest

from mastodon import Mastodon
from google.cloud import firestore


JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
def check_test(data):
    try:
        is_test = data["value"]["fields"]["is_test"]
    except:
        is_test = None
    return is_test


# mastodon
def create_mastodon_client(test=False):
    if test:
        return {}
    else:
        CLIENT_ID = os.environ['CLIENT_ID']
        CLIENT_SECRET = os.environ['CLIENT_SECRET']
        ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
        return Mastodon(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            access_token=ACCESS_TOKEN,
            api_base_url='https://mistodon.cloud'
        )
# firestore
def create_db(test=False):
    if test:
        return {}
    else:
        GCP_PROJECT_ID = os.environ['GCP_PROJECT_ID']
        return firestore.Client(project=GCP_PROJECT_ID)

class Store:
    """
    db関連の処理をするクラス
    今のところはlookupしか実装していない。 
    """

    def __init__(self, db):
        self.db = db

    def find_doc(self, user):
        return db.collection('mist_sita').document(str(user))

    # sitakotoは文字列（リストの時に最初の要素にするのは呼び出し側の責任）
    def lookup(self, user, sitakoto):
        doc_ref = self.find_doc(user)
        return doc_ref.get().to_dict()[str(sitakoto)]

def to_jst(time):
    return (time + datetime.timedelta(hours=9)).replace(tzinfo=JST)

def format_times(time):
        lastTime = time #+ datetime.timedelta(hours=9)
        lastTime_format = lastTime.strftime("%Y/%m/%d %H:%M")
        #前回からの間隔を計算
        now = datetime.datetime.now().replace(tzinfo=JST)
        interval = now - time.replace(tzinfo=JST)
        total_secs = interval.total_seconds()
        days, amari = divmod(total_secs, 24*3600)
        hours, amari = divmod(amari, 3600)
        minutes, secs = divmod(amari, 60)
        int_format = f'{int(days)}日{int(hours)}時間{int(minutes)}分'
        return {'lastTime': str(lastTime_format), 'interval': str(int_format)}

def add_sita(db, user, sitakoto):
    doc_ref = db.collection('mist_sita').document(str(user))
    doc = doc_ref.get()
    sitakoto = sitakoto[0] if type(sitakoto) == list else sitakoto

    
    sitakoto = re.sub('[\?\.\/\[\]\-=`~_]', '＿', urllib.parse.quote_plus(sitakoto))
    if len(sitakoto) > 1500:
        return {'error':'sitaの文字数が多すぎます。'}
    try:
        if doc.exists:
            doc_ref.update({
                f'`{sitakoto}`': firestore.ArrayUnion([datetime.datetime.now()]),
            })
        else:
            doc_ref.set({
                f'{sitakoto}': [datetime.datetime.now()],
            })
        sitakoto_list = doc_ref.get().to_dict()[str(sitakoto)]
        count = len(sitakoto_list)
        if count < 2 :
            last_time = sitakoto_list[-1]
        else:
            last_time = sitakoto_list[-2]
        t = format_times(last_time)
        last_time = t['lastTime']
        interval =  t['interval']
    except:
        count, last_time, interval = 0, 0, 0
        print('例外発生！')
        traceback.print_exc()
    return {'count': count, 'last_time': last_time, 'interval': interval, 'error':'何らかのエラー'}

def add_sita_format(target, sita):
    if sita["count"] == 0:
        return ""
    elif sita["count"] == 1:
        return f'おつパオ\n初めての{target}です。'
    else:
        return f'おつパオ\n{sita["last_time"]}以来、{sita["interval"]}ぶり{sita["count"]}回目の{target}です。'


# noitsu?
def noitsu(user, sitakoto, store):
    sitakoto = sitakoto[0] if type(sitakoto) == list else sitakoto
    sitakoto = re.sub('[\?\.\/\[\]\-=`~_]', '＿', urllib.parse.quote_plus(sitakoto))
    try:
        sitakoto_list = store.lookup(user, sitakoto)
    except KeyError:
        sitakoto_list = {}
    
    count = len(sitakoto_list)

    if count == 0:
        return {"count": 0}
    else:
        t = format_times(sitakoto_list[-1])
        return {'count': count, 'last_time': t['lastTime'], 'interval': t['interval']}

# matome
def matome(user, sitakoto, store):
    sitakoto = sitakoto[0] if type(sitakoto) == list else sitakoto
    sitakoto = re.sub('[\?\.\/\[\]\-=`~_]', '＿',
                      urllib.parse.quote_plus(sitakoto))

    try:
        sitakoto_list = store.lookup(user, sitakoto)
    except KeyError:
        sitakoto_list = {}

    count = len(sitakoto_list)
    if count == 0:
        return {"count": 0}
    elif count == 1:
        first = to_jst(sitakoto_list[0])
        from_first = ((datetime.datetime.now()
                        + datetime.timedelta(hours=9)).replace(tzinfo=JST) - first).days
        return {
            "first": first.strftime("%Y/%m/%d %H:%M"),
            "from_first": from_first,
            "count": 1
        }
    else:
        first, last = to_jst(sitakoto_list[0]), to_jst(sitakoto_list[-1])
        from_first = (last - first).days if (last - first).days != 0 else 1
        from_last = (to_jst(datetime.datetime.now()) - last).days
        m = {
            "first": first.strftime("%Y/%m/%d"),
            "last": last.strftime("%Y/%m/%d"),
            "count": count,
            "from_first": from_first,
            "from_last": from_last,
            "week_ave": format(count / (from_first / 7), ".3f")
        }
        if count >=10:
            before_10 = sitakoto_list[-10]
            from_10 = (last -before_10).days if (last -before_10) != 0 else 1
            m.update({
                "before_10": before_10.strftime("%Y/%m/%d"),
                "from_10_ave": format(10 / (from_10 /7), ".3f")
            })
        return m

def matome_format(target, m):
    res = []
    if m['count'] == 0:
        res.append(f'あなたはまだ{target}をしたことがないようです。')
    elif m['count'] == 1:
        res.append(f'{target}のまとめ')
        res.append(f'初回：{m["first"]}({m["from_first"]}日前)')
    else:
        res.append(f'{target}のまとめ')
        res.append(f'初回：{m["first"]}({m["from_first"]}日前)')
        res.append(f'最新：{m["last"]}({m["from_last"]}日前)')
        res.append(f'した回数：{m["count"]}回')
        res.append(f'1週間の平均回数（全期間）：{m["week_ave"]}')
        if m['count'] >= 10:
            res.append(f'1週間の平均回数（最新10回分）：{m["from_10_ave"]}')
    return '\n'.join(res)

# delete
def deleteall(db, user):
    db.collection("mist_sita").document(user).delete()
    
class StoreMock:

    def __init__(self):
        self.returnValue = {}

    def lookup(self, user, sitakoto):
        self.user = user
        self.sitakoto = sitakoto
        return self.returnValue

class TestSitaKoto(unittest.TestCase):

    def setUp(self):
        self.store = StoreMock()

    def test_firstTime_Normal(self):
        store = self.store
        actual = noitsu("karino2012", "hogehoge", store)
        self.assertEqual('karino2012', store.user)
        self.assertEqual('hogehoge', store.sitakoto)
        self.assertEqual(0, actual['count'])

    def test_firstTime_Magic(self):
        store = self.store
        noitsu("karino2012", "hoge.ika", store)
        self.assertEqual('hoge＿ika', store.sitakoto)

    def test_secondTime(self):
        store = self.store
        tenMinutesBefore = datetime.datetime.now().replace(
            tzinfo=JST) - datetime.timedelta(minutes=10)
        store.returnValue = [tenMinutesBefore]
        actual = noitsu("karino2012", "hogehoge", store)
        self.assertEqual(1, actual['count'])
        self.assertEqual(actual['interval'], '0日0時間10分')

    def test_matome_format_none(self):
        actual = matome_format("hoge", {'count': 0})
        self.assertEqual("あなたはまだhogeをしたことがないようです。", actual)

    def test_matome_format_one(self):
        actual = matome_format(
            "hoge", {'count': 1, 'first': "2022/7/5 12:15", 'from_first': 3})
        self.assertEqual("hogeのまとめ\n初回：2022/7/5 12:15(3日前)", actual)

    def test_matome_format_two(self):
        m = {'count': 2, 'first': "2022/7/1 12:15", 'from_first': 7,
             'last': "2022/7/5 21:11", "from_last": 3, 'week_ave': 0.7}
        actual = matome_format("hoge", m)
        self.assertEqual(
            "hogeのまとめ\n初回：2022/7/1 12:15(7日前)\n最新：2022/7/5 21:11(3日前)\nした回数：2回\n1週間の平均回数（全期間）：0.7", actual)

    def test_add_sita_format_none(self):
        # 何らかのエラーで0が入った場合
        actual = add_sita_format("hoge", {'count': 0})
        self.assertEqual("", actual)

    def test_add_sita_format_one(self):
        actual = add_sita_format("hoge", {'count': 1})
        self.assertEqual("おつパオ\n初めてのhogeです。", actual)

    def test_add_sita_format_two(self):
        actual = add_sita_format(
            "hoge", {'count': 2, "interval": "0日0時間2分", "last_time": "2022/7/5 21:11"})
        self.assertEqual(
            "おつパオ\n2022/7/5 21:11以来、0日0時間2分ぶり2回目のhogeです。", actual)

def unit_test():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSitaKoto)
    runner = unittest.TextTestRunner()
    runner.run(suite)

def reply(data, context):
    global is_test
    is_test = check_test(data)

    if is_test:
        unit_test()
        return None
        
    mastodon = create_mastodon_client(is_test)
    global db
    db = create_db(is_test)
    store = Store(db)
    toot = ""

    notification_id = data["value"]["fields"]["id"]["integerValue"]
    status = mastodon.notifications(id=notification_id)["status"]
    acct = status["account"]["acct"]
    content = status["content"]
    content = re.sub('<.*?>', '', content)
    content = re.sub('@sita', '', content)
    content = content.split()
    
    if not content or status["visibility"] == "direct":
        return None
    elif len(content[0]) > 400:
        mastodon.status_reply(status, "error: sita too long", visibility="unlisted")
        return None
    
    target = None
    command = None

    if len(content) == 1:
        if content[0] == "delete":
            deleteall(id)
            mastodon.status_reply(status, "deleted", visibility="unlisted")
            return None
        else:
            target = content[0]
            sita = add_sita(db, acct, content)
            toot = add_sita_format(target, sita)
    
    elif len(content) >= 2:
        target = content[0]
        command = content[1]
        if command == "のいつ？":
            itsu = noitsu(acct, target, store)
            if itsu["count"] == 0:
                toot = f'あなたはまだ{target}をしたことがないようです。'
            else:
                toot = f'最後に{target}したのは、{itsu["interval"]}前（{itsu["last_time"]}）の{itsu["count"]}回目です。'
        elif command == "まとめ":
            m = matome(acct, content, store)
            toot = matome_format(target, m)
        else:
            sita = add_sita(db, acct, content)
            toot = add_sita_format(target, sita)
    else:
        # ここには来ない想定
        target = content[0]
        sita = add_sita(db, acct, content)
        toot= add_sita_format(target, sita)

    if len(toot) == 0:
        mastodon.status_reply(status, "仕様外の入力です。", visibility="unlisted")
        return None
    
    try:
        reply_text = toot.replace("@", "＠")
        if len(reply_text)>= 450:
            reply_text = reply_text[:450] + "..."
        mastodon.status_reply(status, reply_text, visibility="unlisted")
    except:
        mastodon.status_reply(status, "unknown error", visibility="unlisted")
        traceback.print_exc()
        return toot
    print(content)

if __name__ == "__main__":
    data = {
        "value":{
            "fields": {
                "id" : {
                    "integerValue" : 71402
                },
                "is_test": False
        }
    }
    }
    reply(data, None)