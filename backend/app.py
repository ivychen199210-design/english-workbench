"""
English Workbench 后端服务
基于 FastAPI，提供英语学习 + 个人工作台功能
"""
import sqlite3
import json
import os
import re
import requests
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ==================== 配置 ====================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "workbench.db"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title="English Workbench", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 数据库 ====================
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    # 待办事项
    c.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            priority TEXT DEFAULT 'medium',
            done INTEGER DEFAULT 0,
            due_date TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # 日程时间块
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedule_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            block_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            category TEXT DEFAULT 'work',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # 每日打卡
    c.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkin_date TEXT NOT NULL,
            item_name TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            note TEXT,
            UNIQUE(checkin_date, item_name)
        )
    """)
    # 打卡项目配置
    c.execute("""
        CREATE TABLE IF NOT EXISTS checkin_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#4CAF50'
        )
    """)
    # 单词本
    c.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            meaning TEXT,
            phonetic TEXT,
            example TEXT,
            difficulty TEXT DEFAULT 'medium',
            learned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # 学习记录
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            module TEXT NOT NULL,
            duration_min INTEGER DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ==================== 英语学习素材库 ====================
DAILY_DIALOGUES = [
    {
        "id": 1,
        "topic": "At the Airport",
        "scenario": "Checking in for a flight",
        "dialogue": [
            {"speaker": "Agent", "text": "Good morning! Where are you flying to today?"},
            {"speaker": "You", "text": "I'm flying to London. Here's my passport and ticket."},
            {"speaker": "Agent", "text": "Thank you. Are you checking any bags?"},
            {"speaker": "You", "text": "Yes, just one suitcase. It's under 23 kilograms."},
            {"speaker": "Agent", "text": "Great. Would you like a window or aisle seat?"},
            {"speaker": "You", "text": "A window seat, please. Preferably near the front."},
            {"speaker": "Agent", "text": "Here's your boarding pass. Gate 12, boarding at 3:15 PM. Have a great flight!"},
        ],
        "key_phrases": [
            {"phrase": "checking any bags", "meaning": "托运行李", "usage": "机场值机时询问是否需要托运行李"},
            {"phrase": "window/aisle seat", "meaning": "靠窗/靠过道座位", "usage": "选座时最常用的表达"},
            {"phrase": "boarding pass", "meaning": "登机牌", "usage": "值机后拿到的登机凭证"},
        ],
    },
    {
        "id": 2,
        "topic": "Restaurant Complaint",
        "scenario": "Politely complaining about cold food",
        "dialogue": [
            {"speaker": "You", "text": "Excuse me, I think my soup has gone cold. Could you reheat it?"},
            {"speaker": "Waiter", "text": "I'm so sorry about that. Let me take it back right away."},
            {"speaker": "You", "text": "No problem. Also, could I get some extra bread while I wait?"},
            {"speaker": "Waiter", "text": "Of course. I'll bring it over immediately. Apologies again."},
        ],
        "key_phrases": [
            {"phrase": "gone cold", "meaning": "变凉了", "usage": "委婉表达食物问题，不用 'bad' 或 'terrible'"},
            {"phrase": "Could you reheat it?", "meaning": "能加热一下吗", "usage": "礼貌请求，比 'Make it hot' 更得体"},
            {"phrase": "Apologies again", "meaning": "再次道歉", "usage": "服务方常用的补充道歉"},
        ],
    },
    {
        "id": 3,
        "topic": "Meeting Disagreement",
        "scenario": "Disagreeing politely in a business meeting",
        "dialogue": [
            {"speaker": "Colleague", "text": "I think we should launch next week to beat the competition."},
            {"speaker": "You", "text": "I see your point, but I have some concerns about rushing it."},
            {"speaker": "Colleague", "text": "What kind of concerns?"},
            {"speaker": "You", "text": "Well, the testing phase isn't complete. What if we launch and find bugs?"},
            {"speaker": "Colleague", "text": "That's fair. Maybe we compromise on a soft launch?"},
            {"speaker": "You", "text": "That sounds reasonable. A soft launch would let us gather feedback first."},
        ],
        "key_phrases": [
            {"phrase": "I see your point, but", "meaning": "我理解你的观点，但是", "usage": "先肯定对方再提出异议，非常实用"},
            {"phrase": "What if we...?", "meaning": "如果我们……会怎样？", "usage": "用假设句引导思考，而非直接否定"},
            {"phrase": "That sounds reasonable", "meaning": "这听起来合理", "usage": "接受对方建议时的得体回应"},
        ],
    },
    {
        "id": 4,
        "topic": "Coffee Shop Order",
        "scenario": "Ordering a customised coffee",
        "dialogue": [
            {"speaker": "Barista", "text": "Hi! What can I get for you?"},
            {"speaker": "You", "text": "Could I get a large oat milk latte, please?"},
            {"speaker": "Barista", "text": "Sure. Would you like any syrup in that?"},
            {"speaker": "You", "text": "Yes, one pump of vanilla, please. And make it decaf if possible."},
            {"speaker": "Barista", "text": "No problem. That's £4.50. Name for the cup?"},
            {"speaker": "You", "text": "It's Alex. Thanks!"},
        ],
        "key_phrases": [
            {"phrase": "oat milk latte", "meaning": "燕麦奶拿铁", "usage": "点咖啡时指定奶的种类"},
            {"phrase": "one pump of vanilla", "meaning": "一份香草糖浆", "usage": "控制糖浆用量的地道表达"},
            {"phrase": "make it decaf", "meaning": "要低咖啡因的", "usage": "简短地道的定制要求"},
        ],
    },
    {
        "id": 5,
        "topic": "Doctor's Visit",
        "scenario": "Describing symptoms to a doctor",
        "dialogue": [
            {"speaker": "Doctor", "text": "What seems to be the problem today?"},
            {"speaker": "You", "text": "I've had a sore throat and a mild fever for three days now."},
            {"speaker": "Doctor", "text": "Any coughing or body aches?"},
            {"speaker": "You", "text": "A dry cough, especially at night. And I've been feeling a bit run down."},
            {"speaker": "Doctor", "text": "Sounds like a viral infection. Get plenty of rest and fluids. I'll prescribe something for the throat."},
        ],
        "key_phrases": [
            {"phrase": "sore throat", "meaning": "喉咙痛", "usage": "描述症状的基础表达"},
            {"phrase": "feeling run down", "meaning": "感觉很疲惫", "usage": "比 'tired' 更地道，暗示免疫力下降"},
            {"phrase": "viral infection", "meaning": "病毒感染", "usage": "医生常用术语"},
        ],
    },
    {
        "id": 6,
        "topic": "Job Interview",
        "scenario": "Introducing yourself and strengths",
        "dialogue": [
            {"speaker": "Interviewer", "text": "So, tell me a bit about yourself."},
            {"speaker": "You", "text": "Sure. I've been working in product design for about five years, mostly in fintech."},
            {"speaker": "Interviewer", "text": "What would you say is your greatest strength?"},
            {"speaker": "You", "text": "I'd say it's my ability to turn complex problems into simple, user-friendly solutions."},
            {"speaker": "Interviewer", "text": "Can you give me an example?"},
            {"speaker": "You", "text": "Absolutely. In my last role, I redesigned a dashboard that reduced user confusion by 40%."},
        ],
        "key_phrases": [
            {"phrase": "turn complex problems into simple solutions", "meaning": "把复杂问题变简单方案", "usage": "面试黄金句型，展示思维"},
            {"phrase": "reduced ... by 40%", "meaning": "降低了40%", "usage": "用数据说话，比形容词有力"},
            {"phrase": "greatest strength", "meaning": "最大优势", "usage": "面试高频问题"},
        ],
    },
]

VOCAB_CARDS = [
    {"word": "commute", "phonetic": "/kəˈmjuːt/", "meaning": "通勤；上下班往返", "example": "My commute takes about 45 minutes each way.", "difficulty": "medium"},
    {"word": "overwhelmed", "phonetic": "/ˌəʊvəˈwelmd/", "meaning": "不知所措的；应接不暇的", "example": "I'm feeling a bit overwhelmed by all the tasks this week.", "difficulty": "medium"},
    {"word": "leverage", "phonetic": "/ˈliːvərɪdʒ/", "meaning": "利用；借助", "example": "We should leverage our existing customer base for the new product.", "difficulty": "medium"},
    {"word": "procrastinate", "phonetic": "/prəˈkræstɪneɪt/", "meaning": "拖延", "example": "I tend to procrastinate when the task feels too big.", "difficulty": "hard"},
    {"word": "fluent", "phonetic": "/ˈfluːənt/", "meaning": "流利的；流畅的", "example": "She's fluent in three languages.", "difficulty": "easy"},
    {"word": "articulate", "phonetic": "/ɑːˈtɪkjuleɪt/", "meaning": "清晰地表达", "example": "He articulated his vision clearly to the team.", "difficulty": "hard"},
    {"word": "on the same page", "phonetic": "", "meaning": "达成共识；理解一致", "example": "Let's make sure we're all on the same page before we start.", "difficulty": "medium"},
    {"word": "ballpark figure", "phonetic": "", "meaning": "大概的数字；估计值", "example": "Can you give me a ballpark figure for the budget?", "difficulty": "medium"},
    {"word": "touch base", "phonetic": "", "meaning": "简单沟通；联系一下", "example": "Let's touch base next week to see how it's going.", "difficulty": "easy"},
    {"word": "get the hang of", "phonetic": "", "meaning": "掌握；摸到门道", "example": "It takes practice, but you'll get the hang of it.", "difficulty": "easy"},
    {"word": "call it a day", "phonetic": "", "meaning": "今天就到此为止", "example": "We've done enough. Let's call it a day.", "difficulty": "easy"},
    {"word": "under the weather", "phonetic": "", "meaning": "身体不适", "example": "I'm feeling a bit under the weather today.", "difficulty": "medium"},
    {"word": "break the ice", "phonetic": "", "meaning": "破冰；打破僵局", "example": "He told a joke to break the ice at the meeting.", "difficulty": "easy"},
    {"word": "cost an arm and a leg", "phonetic": "", "meaning": "非常昂贵", "example": "That jacket must have cost an arm and a leg.", "difficulty": "medium"},
    {"word": "piece of cake", "phonetic": "", "meaning": "小菜一碟", "example": "The exam was a piece of cake.", "difficulty": "easy"},
]

ROLEPLAY_SCENARIOS = [
    {"id": 1, "title": "在咖啡店点单", "role": "顾客", "setting": "你走进一家伦敦的咖啡店，需要点一杯定制咖啡", "tips": "尝试使用 'Could I get...', 'make it...', 'one pump of...'"},
    {"id": 2, "title": "酒店前台投诉", "role": "住客", "setting": "房间空调坏了，你需要礼貌地向前台反映并要求换房", "tips": "使用 'I'm afraid...', 'Would it be possible to...', 'I'd appreciate it if...'"},
    {"id": 3, "title": "面试自我介绍", "role": "求职者", "setting": "你正在面试一家科技公司，面试官让你做自我介绍", "tips": "用 'I've been working in...', 'My greatest strength is...', 'For example...'"},
    {"id": 4, "title": "和朋友约饭", "role": "发起人", "setting": "你想约朋友周末吃饭，需要商量时间和地点", "tips": "用 'Are you free...', 'How about...', 'Does ... work for you?'"},
    {"id": 5, "title": "退货", "role": "顾客", "setting": "你在商店想退一件有缺陷的商品，需要向店员说明情况", "tips": "用 'I'd like to return...', 'It's faulty / defective', 'Can I get a refund?'"},
    {"id": 6, "title": "会议上提出新想法", "role": "团队成员", "setting": "你想在团队会议上提出一个新方案，需要说服大家", "tips": "用 'I'd like to propose...', 'The benefit would be...', 'What do you think?'"},
]

# 疑难单词讲解库（用于单词查询）
WORD_EXPLANATIONS = {}
for card in VOCAB_CARDS:
    WORD_EXPLANATIONS[card["word"]] = {
        "word": card["word"],
        "phonetic": card["phonetic"],
        "meaning": card["meaning"],
        "example": card["example"],
        "explanation": f"'{card['word']}' 的意思是「{card['meaning']}」。"
                       f"例句：{card['example']}。"
                       f"这个{'词组' if ' ' in card['word'] else '词'}属于{card['difficulty']}难度，"
                       f"在日常交流和职场中{'很常用' if card['difficulty'] != 'hard' else '偏高级，掌握后会让表达更地道'}。",
    }

# 复述练习材料
RETELL_MATERIALS = [
    {
        "id": 1,
        "title": "A Morning Routine",
        "text": "Every morning, Sarah wakes up at 6:30 and goes for a run in the park. She believes that exercise helps her stay focused throughout the day. After her run, she makes a healthy breakfast — usually oatmeal with berries and a cup of black coffee. Then she spends fifteen minutes reviewing her goals for the day before starting work.",
        "key_points": ["Sarah wakes up at 6:30", "Goes for a run in the park", "Exercise helps her stay focused", "Breakfast: oatmeal, berries, black coffee", "Reviews daily goals for 15 minutes"],
        "difficulty": "easy",
    },
    {
        "id": 2,
        "title": "The Importance of Small Talk",
        "text": "Small talk might seem trivial, but it plays a crucial role in building relationships. In many cultures, discussing the weather or asking about someone's weekend is a way to establish rapport before getting to business. People who master small talk often find it easier to network and build trust in professional settings.",
        "key_points": ["Small talk seems trivial but is important", "Builds relationships", "Weather, weekend topics establish rapport", "Helps with networking and trust in business"],
        "difficulty": "medium",
    },
    {
        "id": 3,
        "title": "Remote Work Challenges",
        "text": "While remote work offers flexibility, it also comes with challenges. Many remote workers struggle with blurred boundaries between work and personal life. Without the natural transitions of an office environment, people often find themselves working longer hours. Experts recommend setting clear work hours, creating a dedicated workspace, and taking regular breaks to maintain productivity and well-being.",
        "key_points": ["Remote work offers flexibility but has challenges", "Blurred work-life boundaries", "People work longer hours", "Experts recommend: clear hours, dedicated workspace, regular breaks"],
        "difficulty": "medium",
    },
]


# ==================== 2岁英语启蒙素材库 ====================

# 26个字母 + 关联词
KIDS_ALPHABET = [
    {"letter": "A", "word": "Apple", "emoji": "🍎", "phonetic": "/ˈæp.əl/"},
    {"letter": "B", "word": "Ball", "emoji": "⚽", "phonetic": "/bɔːl/"},
    {"letter": "C", "word": "Cat", "emoji": "🐱", "phonetic": "/kæt/"},
    {"letter": "D", "word": "Dog", "emoji": "🐶", "phonetic": "/dɒɡ/"},
    {"letter": "E", "word": "Elephant", "emoji": "🐘", "phonetic": "/ˈel.ɪ.fənt/"},
    {"letter": "F", "word": "Fish", "emoji": "🐟", "phonetic": "/fɪʃ/"},
    {"letter": "G", "word": "Giraffe", "emoji": "🦒", "phonetic": "/dʒɪˈrɑːf/"},
    {"letter": "H", "word": "House", "emoji": "🏠", "phonetic": "/haʊs/"},
    {"letter": "I", "word": "Ice cream", "emoji": "🍦", "phonetic": "/aɪs kriːm/"},
    {"letter": "J", "word": "Juice", "emoji": "🧃", "phonetic": "/dʒuːs/"},
    {"letter": "K", "word": "Kite", "emoji": "🪁", "phonetic": "/kaɪt/"},
    {"letter": "L", "word": "Lion", "emoji": "🦁", "phonetic": "/ˈlaɪ.ən/"},
    {"letter": "M", "word": "Monkey", "emoji": "🐵", "phonetic": "/ˈmʌŋ.ki/"},
    {"letter": "N", "word": "Nest", "emoji": "🪺", "phonetic": "/nest/"},
    {"letter": "O", "word": "Orange", "emoji": "🍊", "phonetic": "/ˈɒr.ɪndʒ/"},
    {"letter": "P", "word": "Penguin", "emoji": "🐧", "phonetic": "/ˈpeŋ.ɡwɪn/"},
    {"letter": "Q", "word": "Queen", "emoji": "👸", "phonetic": "/kwiːn/"},
    {"letter": "R", "word": "Rabbit", "emoji": "🐰", "phonetic": "/ˈræb.ɪt/"},
    {"letter": "S", "word": "Sun", "emoji": "☀️", "phonetic": "/sʌn/"},
    {"letter": "T", "word": "Tiger", "emoji": "🐯", "phonetic": "/ˈtaɪ.ɡər/"},
    {"letter": "U", "word": "Umbrella", "emoji": "☂️", "phonetic": "/ʌmˈbrel.ə/"},
    {"letter": "V", "word": "Violin", "emoji": "🎻", "phonetic": "/ˌvaɪ.əˈlɪn/"},
    {"letter": "W", "word": "Whale", "emoji": "🐳", "phonetic": "/weɪl/"},
    {"letter": "X", "word": "X-ray", "emoji": "🩻", "phonetic": "/ˈeks.reɪ/"},
    {"letter": "Y", "word": "Yo-yo", "emoji": "🪀", "phonetic": "/ˈjəʊ.jəʊ/"},
    {"letter": "Z", "word": "Zebra", "emoji": "🦓", "phonetic": "/ˈzeb.rə/"},
]

# 主题词汇
KIDS_THEMES = [
    {
        "theme": "Animals",
        "emoji": "动物园",
        "color": "#FEF3C7",
        "words": [
            {"word": "Dog", "emoji": "🐶", "phonetic": "/dɒɡ/"},
            {"word": "Cat", "emoji": "🐱", "phonetic": "/kæt/"},
            {"word": "Cow", "emoji": "🐮", "phonetic": "/kaʊ/"},
            {"word": "Pig", "emoji": "🐷", "phonetic": "/pɪɡ/"},
            {"word": "Duck", "emoji": "🦆", "phonetic": "/dʌk/"},
            {"word": "Sheep", "emoji": "🐑", "phonetic": "/ʃiːp/"},
            {"word": "Horse", "emoji": "🐴", "phonetic": "/hɔːs/"},
            {"word": "Chicken", "emoji": "🐔", "phonetic": "/ˈtʃɪk.ɪn/"},
            {"word": "Rabbit", "emoji": "🐰", "phonetic": "/ˈræb.ɪt/"},
            {"word": "Bird", "emoji": "🐦", "phonetic": "/bɜːd/"},
        ]
    },
    {
        "theme": "Colors",
        "emoji": "颜色",
        "color": "#DBEAFE",
        "words": [
            {"word": "Red", "emoji": "🔴", "phonetic": "/red/"},
            {"word": "Blue", "emoji": "🔵", "phonetic": "/bluː/"},
            {"word": "Yellow", "emoji": "🟡", "phonetic": "/ˈjel.əʊ/"},
            {"word": "Green", "emoji": "🟢", "phonetic": "/ɡriːn/"},
            {"word": "Orange", "emoji": "🟠", "phonetic": "/ˈɒr.ɪndʒ/"},
            {"word": "Purple", "emoji": "🟣", "phonetic": "/ˈpɜː.pəl/"},
            {"word": "Pink", "emoji": "🩷", "phonetic": "/pɪŋk/"},
            {"word": "Brown", "emoji": "🟤", "phonetic": "/braʊn/"},
            {"word": "Black", "emoji": "⚫", "phonetic": "/blæk/"},
            {"word": "White", "emoji": "⚪", "phonetic": "/waɪt/"},
        ]
    },
    {
        "theme": "Numbers",
        "emoji": "数字",
        "color": "#D1FAE5",
        "words": [
            {"word": "One", "emoji": "1️⃣", "phonetic": "/wʌn/"},
            {"word": "Two", "emoji": "2️⃣", "phonetic": "/tuː/"},
            {"word": "Three", "emoji": "3️⃣", "phonetic": "/θriː/"},
            {"word": "Four", "emoji": "4️⃣", "phonetic": "/fɔːr/"},
            {"word": "Five", "emoji": "5️⃣", "phonetic": "/faɪv/"},
            {"word": "Six", "emoji": "6️⃣", "phonetic": "/sɪks/"},
            {"word": "Seven", "emoji": "7️⃣", "phonetic": "/ˈsev.ən/"},
            {"word": "Eight", "emoji": "8️⃣", "phonetic": "/eɪt/"},
            {"word": "Nine", "emoji": "9️⃣", "phonetic": "/naɪn/"},
            {"word": "Ten", "emoji": "🔟", "phonetic": "/ten/"},
        ]
    },
    {
        "theme": "Food",
        "emoji": "食物",
        "color": "#FED7AA",
        "words": [
            {"word": "Apple", "emoji": "🍎", "phonetic": "/ˈæp.əl/"},
            {"word": "Banana", "emoji": "🍌", "phonetic": "/bəˈnɑː.nə/"},
            {"word": "Bread", "emoji": "🍞", "phonetic": "/bred/"},
            {"word": "Milk", "emoji": "🥛", "phonetic": "/mɪlk/"},
            {"word": "Egg", "emoji": "🥚", "phonetic": "/eɡ/"},
            {"word": "Cake", "emoji": "🍰", "phonetic": "/keɪk/"},
            {"word": "Fish", "emoji": "🐟", "phonetic": "/fɪʃ/"},
            {"word": "Cheese", "emoji": "🧀", "phonetic": "/tʃiːz/"},
            {"word": "Cookie", "emoji": "🍪", "phonetic": "/ˈkʊk.i/"},
            {"word": "Water", "emoji": "💧", "phonetic": "/ˈwɔː.tər/"},
        ]
    },
    {
        "theme": "Body Parts",
        "emoji": "身体",
        "color": "#FCE7F3",
        "words": [
            {"word": "Head", "emoji": "🧑", "phonetic": "/hed/"},
            {"word": "Eye", "emoji": "👁️", "phonetic": "/aɪ/"},
            {"word": "Nose", "emoji": "👃", "phonetic": "/nəʊz/"},
            {"word": "Mouth", "emoji": "👄", "phonetic": "/maʊθ/"},
            {"word": "Ear", "emoji": "👂", "phonetic": "/ɪər/"},
            {"word": "Hand", "emoji": "✋", "phonetic": "/hænd/"},
            {"word": "Foot", "emoji": "🦶", "phonetic": "/fʊt/"},
            {"word": "Arm", "emoji": "💪", "phonetic": "/ɑːm/"},
            {"word": "Leg", "emoji": "🦵", "phonetic": "/leɡ/"},
            {"word": "Tummy", "emoji": "🤰", "phonetic": "/ˈtʌm.i/"},
        ]
    },
]

# 经典儿歌
KIDS_SONGS = [
    {
        "title": "Twinkle Twinkle Little Star",
        "emoji": "Twinkle",
        "bvid": "BV1Yb4y1H7V1",
        "lyrics": [
            "Twinkle, twinkle, little star,",
            "How I wonder what you are!",
            "Up above the world so high,",
            "Like a diamond in the sky.",
            "Twinkle, twinkle, little star,",
            "How I wonder what you are!"
        ],
        "tip": "Sing slowly and do hand gestures — open and close hands like twinkling stars."
    },
    {
        "title": "Old MacDonald Had a Farm",
        "emoji": "Farm",
        "bvid": "BV1jE411F7Xy",
        "lyrics": [
            "Old MacDonald had a farm, E-I-E-I-O!",
            "And on that farm he had a cow, E-I-E-I-O!",
            "With a moo-moo here, and a moo-moo there,",
            "Here a moo, there a moo, everywhere a moo-moo!",
            "Old MacDonald had a farm, E-I-E-I-O!"
        ],
        "tip": "Make animal sounds together! Let your child pick the next animal."
    },
    {
        "title": "Head, Shoulders, Knees and Toes",
        "emoji": "Body",
        "bvid": "BV1Tk4y1q7SF",
        "lyrics": [
            "Head, shoulders, knees and toes, knees and toes!",
            "Head, shoulders, knees and toes, knees and toes!",
            "And eyes, and ears, and mouth, and nose!",
            "Head, shoulders, knees and toes, knees and toes!"
        ],
        "tip": "Touch each body part as you sing. Speed up for fun!"
    },
    {
        "title": "The Wheels on the Bus",
        "emoji": "Bus",
        "bvid": "BV1bK4y1D7CA",
        "lyrics": [
            "The wheels on the bus go round and round,",
            "Round and round, round and round.",
            "The wheels on the bus go round and round,",
            "All through the town!",
            "The doors on the bus go open and shut...",
            "The wipers on the bus go swish swish swish..."
        ],
        "tip": "Use arm movements for wheels spinning, doors opening, and wipers swishing."
    },
    {
        "title": "If You're Happy and You Know It",
        "emoji": "Happy",
        "bvid": "BV1ZJ411W7ZM",
        "lyrics": [
            "If you're happy and you know it, clap your hands! 👏",
            "If you're happy and you know it, clap your hands! 👏",
            "If you're happy and you know it, then your face will surely show it,",
            "If you're happy and you know it, clap your hands! 👏",
            "Stomp your feet! 🦶",
            "Shout hooray! 🙌"
        ],
        "tip": "Do the actions together — clapping, stomping, and cheering!"
    },
    {
        "title": "Baa Baa Black Sheep",
        "emoji": "Sheep",
        "bvid": "BV1hJ411t7Aj",
        "lyrics": [
            "Baa, baa, black sheep, have you any wool?",
            "Yes sir, yes sir, three bags full.",
            "One for the master, one for the dame,",
            "And one for the little boy who lives down the lane.",
            "Baa, baa, black sheep, have you any wool?",
            "Yes sir, yes sir, three bags full."
        ],
        "tip": "Use a soft voice for 'baa baa' and let your child join in."
    },
]

# 儿童动画节目
KIDS_SHOWS = [
    {
        "name": "Super Simple Songs",
        "emoji": "🎶",
        "desc": "全球最受欢迎的英语启蒙儿歌系列，动画生动，语速慢，适合0-4岁。每首歌都有可爱的卡通角色和简单动作。",
        "color": "#FEF3C7",
        "episodes": [
            {"title": "Super Simple Songs 合集 (60分钟)", "bvid": "BV15a5kzaEKG", "desc": "经典SSS儿歌大合集，包含Baby Shark, Hello Song等热门歌曲"},
            {"title": "SSS 分级合集 第1级", "bvid": "BV1M1Ka6WEmP", "desc": "从最简单开始，适合刚接触英语的小朋友"},
            {"title": "One Little Finger", "bvid": "BV1fb421n7BM", "desc": "用手指指身体部位，边唱边学身体词汇"},
            {"title": "Baby Shark Dance", "bvid": "BV1vt421j7G7", "desc": "小朋友最爱的鲨鱼宝宝舞，全家一起跳"},
        ]
    },
    {
        "name": "Yakka Dee",
        "emoji": "🗣️",
        "desc": "BBC出品，每集5分钟教一个单词，用动画+真人反复重复，鼓励小朋友开口说。适合刚开始学说话的小朋友。",
        "color": "#DBEAFE",
        "episodes": [
            {"title": "Yakka Dee S1合集", "bvid": "BV1WN4y1D7Uq", "desc": "第一季完整合集，每集教一个单词，从Banana到Shoes"},
            {"title": "Yakka Dee S2合集", "bvid": "BV1Zy4y1L7Xj", "desc": "第二季，更多日常生活单词"},
            {"title": "Yakka Dee S3合集", "bvid": "BV1iN411H7TQ", "desc": "第三季，进阶词汇和表达"},
        ]
    },
    {
        "name": "Bluey",
        "emoji": "🐶",
        "desc": "澳洲顶级动画片，讲述Bluey一家的温馨故事。语速正常偏快，适合有基础的小朋友，家长一起看也能学到育儿方法。",
        "color": "#D1FAE5",
        "episodes": [
            {"title": "Bluey 英文版 S1合集", "bvid": "BV1uPKp6hEXc", "desc": "第一季英文版，每集6分钟，适合亲子共看"},
            {"title": "Bluey S1 E01 Magic Xylophone", "bvid": "BV1aG411y7zD", "desc": "第一集：神奇木琴，Bluey和Bingo的想象游戏"},
            {"title": "Bluey S1 E02 Hospital", "bvid": "BV1kM4y1D7HG", "desc": "第二集：玩医院游戏，学身体和医生词汇"},
        ]
    },
    {
        "name": "Peppa Pig",
        "emoji": "🐷",
        "desc": "英国经典动画，纯正英式发音，语速慢句子简单。每集5分钟讲一个日常生活小故事，非常适合启蒙阶段。",
        "color": "#FCE7F3",
        "episodes": [
            {"title": "Peppa Pig S1 英文版合集", "bvid": "BV13AgS6DEAB", "desc": "第一季52集完整合集，中英字幕"},
            {"title": "Peppa Pig S1 E01 Muddy Puddles", "bvid": "BV1sW411a7Gx", "desc": "经典第一集：泥坑跳跳，学muddy/clean/boots"},
            {"title": "Peppa Pig S1 E02 Mr Dinosaur", "bvid": "BV1pW411a7gi", "desc": "乔治的恐龙先生丢了，学toy/lost/find"},
        ]
    },
]

# 互动游戏
KIDS_GAMES = [
    {
        "title": "Point to the Color",
        "emoji": "🎨",
        "instruction": "Say a color and ask your child to point to something that color in the room.",
        "examples": ["Point to something RED!", "Point to something BLUE!", "Point to something YELLOW!"],
        "tip": "Start with primary colors (red, blue, yellow) before adding more."
    },
    {
        "title": "Animal Sound Match",
        "emoji": "Animal Sound",
        "instruction": "Make an animal sound and ask your child to say the animal's name in English.",
        "examples": ["What says 'Moo'? → Cow!", "What says 'Meow'? → Cat!", "What says 'Woof'? → Dog!"],
        "tip": "Use toy animals or pictures to make it more visual."
    },
    {
        "title": "Count Everything",
        "emoji": "Count",
        "instruction": "Count everyday objects together in English.",
        "examples": ["Let's count the stairs! 1, 2, 3...", "How many apples? 1, 2!", "Count your fingers! 1-10!"],
        "tip": "Count slowly and use fingers to show the numbers."
    },
    {
        "title": "Touch Your Body",
        "emoji": "🧑",
        "instruction": "Say a body part and ask your child to touch it.",
        "examples": ["Touch your NOSE!", "Touch your EARS!", "Touch your TUMMY!"],
        "tip": "Start with face parts (nose, eyes, ears) then add body parts."
    },
    {
        "title": "What's This?",
        "emoji": "What",
        "instruction": "Point to objects around you and ask 'What's this?' Let your child answer.",
        "examples": ["What's this? → It's a cup!", "What's this? → It's a book!", "What's this? → It's a ball!"],
        "tip": "Use objects your child sees every day. Praise every attempt!"
    },
    {
        "title": "Clap the Syllables",
        "emoji": "👏",
        "instruction": "Say a word and clap once for each syllable together.",
        "examples": ["Ap-ple → 👏👏 (2 claps)", "Ba-na-na → 👏👏👏 (3 claps)", "Cat → 👏 (1 clap)"],
        "tip": "Great for developing phonological awareness. Keep it playful!"
    },
]


# ==================== BBC 英语学习素材 ====================
BBC_RESOURCES = [
    {
        "name": "6 Minute English",
        "emoji": "6MIN",
        "desc": "BBC经典英语学习节目，每期6分钟聊一个话题。两位主持人轻松对话，穿插关键词汇讲解。适合中级以上学习者。",
        "color": "#DBEAFE",
        "episodes": [
            {"title": "6 Minute English 2024 合集", "bvid": "BV1jYC6YREbg", "desc": "2024年全年合集，涵盖科技/文化/健康等话题"},
            {"title": "6 Minute English 2023 合集", "bvid": "BV1ej411L7Fh", "desc": "2023年合集，经典话题回顾"},
        ]
    },
    {
        "name": "News Review",
        "emoji": "NEWS",
        "desc": "BBC新闻热点学词汇，每期分析一则真实新闻，讲解关键词汇和表达。适合中高级学习者。",
        "color": "#FEF3C7",
        "episodes": [
            {"title": "BBC Global News Podcast (每日更新)", "bvid": "BV122ge6NETp", "desc": "每日BBC全球新闻播客，练听力+了解时事"},
            {"title": "BBC Newsround 2025 合集", "bvid": "BV1fgYhzQEbY", "desc": "BBC儿童新闻，语速慢用词简单，适合中初级"},
        ]
    },
]

# ==================== 影子跟读内置素材 ====================
SHADOWING_MATERIALS = [
    {
        "id": 1,
        "title": "Daily Routine",
        "level": "Easy",
        "sentences": [
            "I wake up at seven o'clock every morning.",
            "First, I brush my teeth and wash my face.",
            "Then I have breakfast with my family.",
            "After breakfast, I get dressed for work.",
            "I usually leave the house at eight thirty.",
            "My commute takes about forty minutes.",
        ],
        "tip": "Slow down on 'usually' and 'commute'. Pay attention to linking: 'wake up at' → 'wake-up-at'."
    },
    {
        "id": 2,
        "title": "At a Restaurant",
        "level": "Easy",
        "sentences": [
            "I'd like to make a reservation for two people.",
            "We have a table available by the window.",
            "Could I see the menu, please?",
            "I'll have the grilled chicken with vegetables.",
            "The food here is absolutely delicious.",
            "Can we get the bill when you have a moment?",
        ],
        "tip": "Focus on polite intonation. 'Could I...' and 'I'd like...' should sound gentle, not demanding."
    },
    {
        "id": 3,
        "title": "Talking About Weather",
        "level": "Medium",
        "sentences": [
            "It looks like it's going to rain this afternoon.",
            "The temperature has been rising steadily all week.",
            "We had a thunderstorm last night that woke everyone up.",
            "I prefer autumn because the weather is mild and comfortable.",
            "The forecast says we might get some snow tomorrow.",
            "It's absolutely freezing outside, don't forget your coat.",
        ],
        "tip": "Practice linking words: 'it's going to' → 'it's gonna'. Watch the rising intonation on questions."
    },
    {
        "id": 4,
        "title": "Job Interview",
        "level": "Medium",
        "sentences": [
            "I've been working in marketing for over five years.",
            "My greatest strength is my ability to work under pressure.",
            "I'm particularly interested in the company's international expansion.",
            "Could you tell me more about the day-to-day responsibilities?",
            "I believe my experience aligns well with this position.",
            "Thank you for taking the time to meet with me today.",
        ],
        "tip": "Emphasize key words: 'five years', 'greatest strength', 'particularly interested'. Sound confident but not arrogant."
    },
    {
        "id": 5,
        "title": "Giving a Presentation",
        "level": "Hard",
        "sentences": [
            "Good morning everyone, thank you for being here today.",
            "I'd like to start by giving you a brief overview of our project.",
            "As you can see from the data, our revenue has grown significantly.",
            "The key takeaway here is that customer satisfaction has improved.",
            "I'd be happy to answer any questions you might have.",
            "Let me conclude by summarizing the main points we've covered.",
        ],
        "tip": "Pause briefly between sentences. Use hand gestures to emphasize points. Vary your pitch to keep it engaging."
    },
]


# ==================== 数据模型 ====================
class TodoCreate(BaseModel):
    title: str
    category: str = "general"
    priority: str = "medium"
    due_date: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    done: Optional[int] = None
    due_date: Optional[str] = None

class ScheduleBlockCreate(BaseModel):
    title: str
    block_date: str
    start_time: str
    end_time: str
    category: str = "work"
    notes: Optional[str] = None

class CheckinItemCreate(BaseModel):
    name: str
    color: str = "#4CAF50"

class CheckinToggle(BaseModel):
    checkin_date: str
    item_name: str
    done: int
    note: Optional[str] = None

class VocabAdd(BaseModel):
    word: str
    meaning: Optional[str] = None
    phonetic: Optional[str] = None
    example: Optional[str] = None
    difficulty: str = "medium"

class StudyLogCreate(BaseModel):
    module: str
    duration_min: int = 0
    note: Optional[str] = None


# ==================== 英语学习 API ====================

def fetch_free_dictionary(word: str):
    """调用 Free Dictionary API 获取单词释义"""
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower().strip()}"
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or not isinstance(data, list):
            return None
        entry = data[0]
        word_text = entry.get("word", word)
        phonetic = ""
        audio = ""
        for p in entry.get("phonetics", []):
            if p.get("text"):
                phonetic = p.get("text")
            if p.get("audio"):
                audio = p.get("audio")
                break
        # 释义和例句
        meanings = []
        for m in entry.get("meanings", []):
            part = m.get("partOfSpeech", "")
            defs = []
            for d in m.get("definitions", [])[:3]:  # 每种词性最多3条释义
                defs.append({
                    "definition": d.get("definition", ""),
                    "example": d.get("example", ""),
                    "synonyms": d.get("synonyms", [])[:3]
                })
            if defs:
                meanings.append({"partOfSpeech": part, "definitions": defs})
        return {
            "word": word_text,
            "phonetic": phonetic,
            "audio": audio,
            "meanings": meanings,
            "source": "Free Dictionary API"
        }
    except Exception as e:
        print("dictionary api error:", e)
        return None

@app.get("/api/dialogues")
def get_dialogues():
    """获取所有每日对话"""
    return DAILY_DIALOGUES

@app.get("/api/dialogues/{dialogue_id}")
def get_dialogue(dialogue_id: int):
    for d in DAILY_DIALOGUES:
        if d["id"] == dialogue_id:
            return d
    raise HTTPException(404, "Dialogue not found")

@app.get("/api/vocab-cards")
def get_vocab_cards():
    """获取词汇卡片"""
    return VOCAB_CARDS

@app.get("/api/roleplay")
def get_roleplay():
    """获取情景角色扮演场景"""
    return ROLEPLAY_SCENARIOS

@app.get("/api/retell")
def get_retell_materials():
    """获取复述练习材料"""
    return RETELL_MATERIALS


# ==================== 2岁启蒙 API ====================

@app.get("/api/kids/alphabet")
def get_kids_alphabet():
    """获取字母学习数据"""
    return KIDS_ALPHABET

@app.get("/api/kids/themes")
def get_kids_themes():
    """获取主题词汇数据"""
    return KIDS_THEMES

@app.get("/api/kids/songs")
def get_kids_songs():
    """获取儿歌数据"""
    return KIDS_SONGS

@app.get("/api/kids/games")
def get_kids_games():
    """获取互动游戏数据"""
    return KIDS_GAMES

@app.get("/api/kids/shows")
def get_kids_shows():
    """获取儿童动画节目数据"""
    return KIDS_SHOWS

@app.get("/api/bbc")
def get_bbc_resources():
    """获取BBC英语学习资源"""
    return BBC_RESOURCES

@app.get("/api/shadowing")
def get_shadowing_materials():
    """获取影子跟读素材"""
    return SHADOWING_MATERIALS

@app.get("/api/shadowing/{sid}")
def get_shadowing_material(sid: int):
    for m in SHADOWING_MATERIALS:
        if m["id"] == sid:
            return m
    raise HTTPException(404, "Material not found")


@app.get("/api/word-explain/{word}")
def explain_word(word: str):
    word_lower = word.lower().strip()

    # 1. 先查内置词库
    if word_lower in WORD_EXPLANATIONS:
        return WORD_EXPLANATIONS[word_lower]
    for key, val in WORD_EXPLANATIONS.items():
        if word_lower in key or key in word_lower:
            return val

    # 2. 内置没有，调 Free Dictionary API
    dict_data = fetch_free_dictionary(word)
    if dict_data:
        # 组装中文释义（取第一条释义）
        first_meaning = ""
        example = ""
        if dict_data["meanings"] and dict_data["meanings"][0]["definitions"]:
            first = dict_data["meanings"][0]["definitions"][0]
            first_meaning = first.get("definition", "")
            example = first.get("example", "")
        explanation = f"'{dict_data['word']}' 来自 Free Dictionary API。"
        if dict_data["phonetic"]:
            explanation += f"音标：{dict_data['phonetic']}。"
        if first_meaning:
            explanation += f"释义：{first_meaning}"
        return {
            "word": dict_data["word"],
            "phonetic": dict_data["phonetic"],
            "meaning": first_meaning,
            "example": example,
            "audio": dict_data.get("audio", ""),
            "meanings": dict_data["meanings"],
            "explanation": explanation,
            "source": "Free Dictionary API"
        }

    # 3. 都没有
    return {
        "word": word,
        "phonetic": "",
        "meaning": "未找到该单词的释义",
        "example": "",
        "audio": "",
        "explanation": f"'{word}' 暂未在素材库和在线词典中找到。建议：\n1. 检查拼写是否正确\n2. 目前支持英文单词查询\n3. 也可以手动添加到单词本",
    }


# ==================== 单词本 API ====================

@app.get("/api/vocabulary")
def get_vocabulary():
    conn = get_db()
    rows = conn.execute("SELECT * FROM vocabulary ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/vocabulary")
def add_vocabulary(v: VocabAdd):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO vocabulary (word, meaning, phonetic, example, difficulty) VALUES (?,?,?,?,?)",
            (v.word, v.meaning, v.phonetic, v.example, v.difficulty)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(400, str(e))
    conn.close()
    return {"status": "ok"}

@app.put("/api/vocabulary/{vid}/learned")
def mark_learned(vid: int, learned: int = 1):
    conn = get_db()
    conn.execute("UPDATE vocabulary SET learned=? WHERE id=?", (learned, vid))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.delete("/api/vocabulary/{vid}")
def delete_vocabulary(vid: int):
    conn = get_db()
    conn.execute("DELETE FROM vocabulary WHERE id=?", (vid,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ==================== 待办清单 API ====================

@app.get("/api/todos")
def get_todos(category: Optional[str] = None):
    conn = get_db()
    if category:
        rows = conn.execute("SELECT * FROM todos WHERE category=? ORDER BY done, created_at DESC", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM todos ORDER BY done, created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/todos")
def create_todo(todo: TodoCreate):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO todos (title, category, priority, due_date) VALUES (?,?,?,?)",
        (todo.title, todo.category, todo.priority, todo.due_date)
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM todos WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/todos/{tid}")
def update_todo(tid: int, todo: TodoUpdate):
    conn = get_db()
    fields = []
    values = []
    for f in ["title", "category", "priority", "done", "due_date"]:
        val = getattr(todo, f)
        if val is not None:
            fields.append(f"{f}=?")
            values.append(val)
    if fields:
        values.append(tid)
        conn.execute(f"UPDATE todos SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    row = conn.execute("SELECT * FROM todos WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row) if row else {}

@app.delete("/api/todos/{tid}")
def delete_todo(tid: int):
    conn = get_db()
    conn.execute("DELETE FROM todos WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ==================== 日程时间块 API ====================

@app.get("/api/schedule")
def get_schedule(block_date: Optional[str] = None):
    conn = get_db()
    if block_date:
        rows = conn.execute("SELECT * FROM schedule_blocks WHERE block_date=? ORDER BY start_time", (block_date,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM schedule_blocks ORDER BY block_date, start_time").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/schedule")
def create_block(block: ScheduleBlockCreate):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO schedule_blocks (title, block_date, start_time, end_time, category, notes) VALUES (?,?,?,?,?,?)",
        (block.title, block.block_date, block.start_time, block.end_time, block.category, block.notes)
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM schedule_blocks WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return dict(row)

@app.delete("/api/schedule/{sid}")
def delete_block(sid: int):
    conn = get_db()
    conn.execute("DELETE FROM schedule_blocks WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ==================== 每日打卡 API ====================

@app.get("/api/checkin-items")
def get_checkin_items():
    conn = get_db()
    rows = conn.execute("SELECT * FROM checkin_items ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/checkin-items")
def add_checkin_item(item: CheckinItemCreate):
    conn = get_db()
    try:
        conn.execute("INSERT INTO checkin_items (name, color) VALUES (?,?)", (item.name, item.color))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(400, "项目已存在")
    conn.close()
    return {"status": "ok"}

@app.delete("/api/checkin-items/{name}")
def delete_checkin_item(name: str):
    conn = get_db()
    conn.execute("DELETE FROM checkin_items WHERE name=?", (name,))
    conn.execute("DELETE FROM checkins WHERE item_name=?", (name,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/checkins")
def get_checkins(checkin_date: Optional[str] = None):
    conn = get_db()
    if checkin_date:
        rows = conn.execute("SELECT * FROM checkins WHERE checkin_date=? ORDER BY item_name", (checkin_date,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM checkins ORDER BY checkin_date DESC, item_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/checkins/toggle")
def toggle_checkin(data: CheckinToggle):
    conn = get_db()
    existing = conn.execute("SELECT * FROM checkins WHERE checkin_date=? AND item_name=?", (data.checkin_date, data.item_name)).fetchone()
    if existing:
        conn.execute("UPDATE checkins SET done=?, note=? WHERE checkin_date=? AND item_name=?", (data.done, data.note, data.checkin_date, data.item_name))
    else:
        conn.execute("INSERT INTO checkins (checkin_date, item_name, done, note) VALUES (?,?,?,?)", (data.checkin_date, data.item_name, data.done, data.note))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/checkins/stats")
def get_checkin_stats():
    """获取打卡统计"""
    conn = get_db()
    items = conn.execute("SELECT * FROM checkin_items").fetchall()
    stats = []
    for item in items:
        total = conn.execute("SELECT COUNT(*) as c FROM checkins WHERE item_name=? AND done=1", (item["name"],)).fetchone()["c"]
        stats.append({"name": item["name"], "color": item["color"], "total_done": total})
    conn.close()
    return stats


# ==================== 学习记录 API ====================

@app.post("/api/study-log")
def add_study_log(log: StudyLogCreate):
    conn = get_db()
    today = date.today().isoformat()
    conn.execute("INSERT INTO study_log (log_date, module, duration_min, note) VALUES (?,?,?,?)", (today, log.module, log.duration_min, log.note))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/study-log")
def get_study_log():
    conn = get_db()
    rows = conn.execute("SELECT * FROM study_log ORDER BY log_date DESC, id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/dashboard")
def get_dashboard():
    """仪表盘汇总数据"""
    conn = get_db()
    today = date.today().isoformat()
    todos_today = conn.execute("SELECT COUNT(*) as c FROM todos WHERE done=0").fetchone()["c"]
    todos_done = conn.execute("SELECT COUNT(*) as c FROM todos WHERE done=1").fetchone()["c"]
    blocks_today = conn.execute("SELECT * FROM schedule_blocks WHERE block_date=? ORDER BY start_time", (today,)).fetchall()
    checkins_today = conn.execute("SELECT * FROM checkins WHERE checkin_date=? AND done=1", (today,)).fetchall()
    vocab_total = conn.execute("SELECT COUNT(*) as c FROM vocabulary").fetchone()["c"]
    vocab_learned = conn.execute("SELECT COUNT(*) as c FROM vocabulary WHERE learned=1").fetchone()["c"]
    study_logs = conn.execute("SELECT * FROM study_log ORDER BY log_date DESC LIMIT 7").fetchall()
    conn.close()
    return {
        "date": today,
        "todos_pending": todos_today,
        "todos_completed": todos_done,
        "blocks_today": [dict(r) for r in blocks_today],
        "checkins_today_count": len(checkins_today),
        "vocab_total": vocab_total,
        "vocab_learned": vocab_learned,
        "recent_study": [dict(r) for r in study_logs],
    }


# ==================== 静态文件服务 ====================
if FRONTEND_DIR.exists():
    # 挂载所有前端静态文件到根路径
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
