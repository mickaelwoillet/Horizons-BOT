"""Capsules collectives : opt-in, modération, restitution après 90 jours."""
from datetime import datetime, timedelta, timezone
from .storage import db


def utcnow():
    return datetime.now(timezone.utc)


def current_question(guild_id):
    month = utcnow().strftime('%Y-%m')
    with db() as conn:
        return conn.execute('SELECT * FROM collective_capsule_questions WHERE guild_id=? AND month_key=?', (guild_id,month)).fetchone()


def set_question(guild_id, staff_id, question):
    question = question.strip()
    if not 1 <= len(question) <= 250:
        raise ValueError('La question doit contenir entre 1 et 250 caractères.')
    now = utcnow()
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM collective_capsule_questions WHERE guild_id=? AND month_key=?', (guild_id,now.strftime('%Y-%m'))).fetchone():
            raise ValueError('Une question existe déjà pour ce mois. Elle ne peut pas être remplacée.')
        conn.execute('INSERT INTO collective_capsule_questions(guild_id,month_key,question,created_by,created_at,reveal_at) VALUES(?,?,?,?,?,?)',
                     (guild_id,now.strftime('%Y-%m'),question,staff_id,now.isoformat(),(now+timedelta(days=90)).isoformat()))


def submit(guild_id,user_id,content):
    content = content.strip()
    if not 1 <= len(content) <= 700:
        raise ValueError('Ta réponse doit contenir entre 1 et 700 caractères.')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        month = utcnow().strftime('%Y-%m')
        q = conn.execute('SELECT id FROM collective_capsule_questions WHERE guild_id=? AND month_key=?',(guild_id,month)).fetchone()
        if not q:
            raise ValueError('Aucune question collective ouverte ce mois-ci.')
        if conn.execute('SELECT 1 FROM collective_capsule_answers WHERE question_id=? AND user_id=?',(q['id'],user_id)).fetchone():
            raise ValueError('Tu as déjà répondu à cette capsule. Tu peux retirer ta contribution depuis ton Centre.')
        conn.execute('INSERT INTO collective_capsule_answers(question_id,guild_id,user_id,content,created_at) VALUES(?,?,?,?,?)',
                     (q['id'],guild_id,user_id,content,utcnow().isoformat()))


def my_answers(guild_id,user_id):
    with db() as conn:
        return conn.execute('SELECT a.id,a.status,q.month_key,q.reveal_at FROM collective_capsule_answers a JOIN collective_capsule_questions q ON q.id=a.question_id WHERE a.guild_id=? AND a.user_id=? ORDER BY a.id DESC LIMIT 25',(guild_id,user_id)).fetchall()


def withdraw(guild_id,user_id,answer_id):
    with db() as conn:
        return conn.execute('DELETE FROM collective_capsule_answers WHERE id=? AND guild_id=? AND user_id=?',(answer_id,guild_id,user_id)).rowcount>0


def pending(guild_id):
    with db() as conn:
        return conn.execute('SELECT a.id,a.user_id,a.content,q.question FROM collective_capsule_answers a JOIN collective_capsule_questions q ON q.id=a.question_id WHERE a.guild_id=? AND a.status=? ORDER BY a.id LIMIT 10',(guild_id,'pending')).fetchall()


def moderate(guild_id,staff_id,answer_id,approve):
    with db() as conn:
        return conn.execute('UPDATE collective_capsule_answers SET status=?,reviewed_by=?,reviewed_at=? WHERE id=? AND guild_id=? AND status=?',
                            ('approved' if approve else 'rejected',staff_id,utcnow().isoformat(),answer_id,guild_id,'pending')).rowcount>0


def revealed(guild_id,month_key):
    with db() as conn:
        return conn.execute('SELECT a.id,a.content FROM collective_capsule_answers a JOIN collective_capsule_questions q ON q.id=a.question_id WHERE q.guild_id=? AND q.month_key=? AND q.reveal_at<=? AND a.status=? ORDER BY a.id LIMIT 25',
                            (guild_id,month_key,utcnow().isoformat(),'approved')).fetchall()
