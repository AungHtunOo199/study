#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
My Study Assistant Bot v1
- 6 separate subjects
- Subject names can be changed from the bot
- Notes, photos and documents are stored per subject
- View and delete saved items
- SQLite database (survives bot restarts)
- Each Telegram user has separate data

Install:
    pip install pyTelegramBotAPI

Run:
    python study.py
"""

import asyncio
import os
import sqlite3
from datetime import datetime

from telebot.async_telebot import AsyncTeleBot
from telebot import types


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8928989911:AAFEZN_fxLEvip0rrgTR5QCbEmvzX00JCYE"
DB_FILE = "study_assistant.db"

DEFAULT_SUBJECTS = {
    1: "Subject 1",
    2: "Subject 2",
    3: "Subject 3",
    4: "Subject 4",
    5: "Subject 5",
    6: "Subject 6",
}


# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS subjects (
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (user_id, subject_id)
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    file_id TEXT,
    caption TEXT,
    created_at TEXT NOT NULL
)
""")

db.commit()


def init_user(user_id: int):
    for subject_id, name in DEFAULT_SUBJECTS.items():
        db.execute(
            """
            INSERT OR IGNORE INTO subjects (user_id, subject_id, name)
            VALUES (?, ?, ?)
            """,
            (user_id, subject_id, name),
        )
    db.commit()


def get_subjects(user_id: int):
    init_user(user_id)
    return db.execute(
        "SELECT * FROM subjects WHERE user_id = ? ORDER BY subject_id",
        (user_id,),
    ).fetchall()


def get_subject(user_id: int, subject_id: int):
    init_user(user_id)
    return db.execute(
        """
        SELECT * FROM subjects
        WHERE user_id = ? AND subject_id = ?
        """,
        (user_id, subject_id),
    ).fetchone()


def rename_subject(user_id: int, subject_id: int, new_name: str):
    db.execute(
        """
        UPDATE subjects SET name = ?
        WHERE user_id = ? AND subject_id = ?
        """,
        (new_name, user_id, subject_id),
    )
    db.commit()


def add_item(
    user_id: int,
    subject_id: int,
    item_type: str,
    file_id: str | None,
    caption: str | None,
):
    cur = db.execute(
        """
        INSERT INTO items
        (user_id, subject_id, item_type, file_id, caption, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            subject_id,
            item_type,
            file_id,
            caption,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    db.commit()
    return cur.lastrowid


def get_items(user_id: int, subject_id: int, item_type: str | None = None):
    if item_type:
        return db.execute(
            """
            SELECT * FROM items
            WHERE user_id = ? AND subject_id = ? AND item_type = ?
            ORDER BY id DESC
            """,
            (user_id, subject_id, item_type),
        ).fetchall()

    return db.execute(
        """
        SELECT * FROM items
        WHERE user_id = ? AND subject_id = ?
        ORDER BY id DESC
        """,
        (user_id, subject_id),
    ).fetchall()


def get_item(user_id: int, item_id: int):
    return db.execute(
        """
        SELECT * FROM items
        WHERE id = ? AND user_id = ?
        """,
        (item_id, user_id),
    ).fetchone()


def delete_item(user_id: int, item_id: int):
    db.execute(
        """
        DELETE FROM items
        WHERE id = ? AND user_id = ?
        """,
        (item_id, user_id),
    )
    db.commit()


# ============================================================
# BOT / STATE
# ============================================================

bot = AsyncTeleBot(BOT_TOKEN)

# Simple per-user temporary state.
# state[user_id] = {"action": "...", "subject_id": 1}
state = {}


def clear_state(user_id: int):
    state.pop(user_id, None)


def set_state(user_id: int, action: str, subject_id: int | None = None):
    state[user_id] = {
        "action": action,
        "subject_id": subject_id,
    }


# ============================================================
# KEYBOARDS
# ============================================================

def subjects_keyboard(user_id: int):
    kb = types.InlineKeyboardMarkup()
    subjects = get_subjects(user_id)

    for i in range(0, 6, 2):
        row = []
        for subject in subjects[i:i + 2]:
            row.append(
                types.InlineKeyboardButton(
                    f"{subject['subject_id']}️⃣ {subject['name']}",
                    callback_data=f"sub:{subject['subject_id']}",
                )
            )
        kb.row(*row)

    kb.row(
        types.InlineKeyboardButton(
            "⚙️ Change Subject Names",
            callback_data="rename_menu",
        )
    )
    return kb


def subject_keyboard(subject_id: int):
    kb = types.InlineKeyboardMarkup()

    kb.row(
        types.InlineKeyboardButton("📝 Notes", callback_data=f"list:{subject_id}:note"),
        types.InlineKeyboardButton("🖼 Photos", callback_data=f"list:{subject_id}:photo"),
    )
    kb.row(
        types.InlineKeyboardButton("📄 Files", callback_data=f"list:{subject_id}:file"),
        types.InlineKeyboardButton("📚 All", callback_data=f"list:{subject_id}:all"),
    )
    kb.row(
        types.InlineKeyboardButton("➕ Add Note", callback_data=f"addnote:{subject_id}"),
        types.InlineKeyboardButton("🖼 Add Photo", callback_data=f"addphoto:{subject_id}"),
    )
    kb.row(
        types.InlineKeyboardButton("📄 Add File", callback_data=f"addfile:{subject_id}"),
    )
    kb.row(
        types.InlineKeyboardButton("✏️ Rename Subject", callback_data=f"rename:{subject_id}"),
    )
    kb.row(
        types.InlineKeyboardButton("🔄 Switch Subject", callback_data="subjects"),
    )
    return kb


def item_keyboard(item_id: int, subject_id: int):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(
            "🗑 Delete",
            callback_data=f"delete:{item_id}:{subject_id}",
        ),
        types.InlineKeyboardButton(
            "⬅️ Back",
            callback_data=f"sub:{subject_id}",
        ),
    )
    return kb


# ============================================================
# TEXT HELPERS
# ============================================================

def subject_text(user_id: int, subject_id: int):
    subject = get_subject(user_id, subject_id)
    if not subject:
        return "❌ Subject not found."

    items = get_items(user_id, subject_id)

    notes = sum(1 for x in items if x["item_type"] == "note")
    photos = sum(1 for x in items if x["item_type"] == "photo")
    files = sum(1 for x in items if x["item_type"] == "file")

    return (
        f"📚 <b>{subject['name']}</b>\n\n"
        f"📝 Notes: {notes}\n"
        f"🖼 Photos: {photos}\n"
        f"📄 Files: {files}\n\n"
        "Choose an option below:"
    )


# ============================================================
# /START
# ============================================================

@bot.message_handler(commands=["start"])
async def start(message):
    user_id = message.from_user.id
    init_user(user_id)
    clear_state(user_id)

    text = (
        "🎓 <b>MY STUDY ASSISTANT</b>\n\n"
        "📚 Choose a subject:\n\n"
        "Each subject has its own Notes, Photos and Files."
    )

    await bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=subjects_keyboard(user_id),
    )


# ============================================================
# CALLBACKS
# ============================================================

@bot.callback_query_handler(func=lambda call: True)
async def callbacks(call):
    user_id = call.from_user.id
    data = call.data

    init_user(user_id)

    try:
        await bot.answer_callback_query(call.id)
    except Exception:
        pass

    # -------------------------
    # Subject menu
    # -------------------------
    if data == "subjects":
        clear_state(user_id)
        await bot.edit_message_text(
            "🎓 <b>MY STUDY ASSISTANT</b>\n\n📚 Choose a subject:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=subjects_keyboard(user_id),
        )
        return

    # -------------------------
    # Open subject
    # -------------------------
    if data.startswith("sub:"):
        subject_id = int(data.split(":")[1])
        clear_state(user_id)

        await bot.edit_message_text(
            subject_text(user_id, subject_id),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=subject_keyboard(subject_id),
        )
        return

    # -------------------------
    # Rename menu
    # -------------------------
    if data == "rename_menu":
        kb = types.InlineKeyboardMarkup()

        for i in range(1, 7):
            subject = get_subject(user_id, i)
            kb.add(
                types.InlineKeyboardButton(
                    f"✏️ {i}. {subject['name']}",
                    callback_data=f"rename:{i}",
                )
            )

        kb.row(
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data="subjects",
            )
        )

        await bot.edit_message_text(
            "⚙️ <b>Change Subject Name</b>\n\n"
            "Choose the subject you want to rename:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # -------------------------
    # Rename a subject
    # -------------------------
    if data.startswith("rename:"):
        subject_id = int(data.split(":")[1])
        subject = get_subject(user_id, subject_id)

        set_state(user_id, "rename_subject", subject_id)

        await bot.send_message(
            call.message.chat.id,
            f"✏️ Current name: <b>{subject['name']}</b>\n\n"
            "Send the new subject name.\n"
            "Example: <code>Marketing</code>\n\n"
            "Send /cancel to cancel.",
            parse_mode="HTML",
        )
        return

    # -------------------------
    # Add note
    # -------------------------
    if data.startswith("addnote:"):
        subject_id = int(data.split(":")[1])
        set_state(user_id, "add_note", subject_id)

        await bot.send_message(
            call.message.chat.id,
            "📝 <b>Add Note</b>\n\n"
            "Send your note now.\n"
            "You can send multiple lines.\n\n"
            "Send /cancel to cancel.",
            parse_mode="HTML",
        )
        return

    # -------------------------
    # Add photo
    # -------------------------
    if data.startswith("addphoto:"):
        subject_id = int(data.split(":")[1])
        set_state(user_id, "add_photo", subject_id)

        await bot.send_message(
            call.message.chat.id,
            "🖼 <b>Add Photo</b>\n\n"
            "Send the photo now.\n"
            "You can optionally add a caption.\n\n"
            "Send /cancel to cancel.",
            parse_mode="HTML",
        )
        return

    # -------------------------
    # Add file
    # -------------------------
    if data.startswith("addfile:"):
        subject_id = int(data.split(":")[1])
        set_state(user_id, "add_file", subject_id)

        await bot.send_message(
            call.message.chat.id,
            "📄 <b>Add File</b>\n\n"
            "Send a PDF, DOCX, PPTX or other document now.\n"
            "You can optionally add a caption.\n\n"
            "Send /cancel to cancel.",
            parse_mode="HTML",
        )
        return

    # -------------------------
    # List items
    # -------------------------
    if data.startswith("list:"):
        _, subject_id_str, item_type = data.split(":")
        subject_id = int(subject_id_str)

        items = get_items(
            user_id,
            subject_id,
            None if item_type == "all" else item_type,
        )

        subject = get_subject(user_id, subject_id)

        if not items:
            text = (
                f"📚 <b>{subject['name']}</b>\n\n"
                "Nothing saved here yet."
            )
        else:
            title = {
                "note": "📝 Notes",
                "photo": "🖼 Photos",
                "file": "📄 Files",
                "all": "📚 All Items",
            }.get(item_type, "Items")

            lines = [f"📚 <b>{subject['name']}</b>", f"\n{title}\n"]

            for item in items[:50]:
                icon = {
                    "note": "📝",
                    "photo": "🖼",
                    "file": "📄",
                }.get(item["item_type"], "📌")

                caption = item["caption"] or "(no text)"
                caption = caption.replace("\n", " ")[:60]

                lines.append(
                    f"{icon} <b>#{item['id']}</b> — {caption}"
                )

            if len(items) > 50:
                lines.append("\nShowing latest 50 items.")

            text = "\n".join(lines)

        kb = types.InlineKeyboardMarkup()

        for item in items[:50]:
            icon = {
                "note": "📝",
                "photo": "🖼",
                "file": "📄",
            }.get(item["item_type"], "📌")

            label = (item["caption"] or f"Item #{item['id']}")[:35]

            kb.row(
                types.InlineKeyboardButton(
                    f"{icon} {label}",
                    callback_data=f"view:{item['id']}:{subject_id}",
                )
            )

        kb.row(
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data=f"sub:{subject_id}",
            ),
            types.InlineKeyboardButton(
                "🔄 Subjects",
                callback_data="subjects",
            ),
        )

        await bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # -------------------------
    # View item
    # -------------------------
    if data.startswith("view:"):
        _, item_id_str, subject_id_str = data.split(":")
        item_id = int(item_id_str)
        subject_id = int(subject_id_str)

        item = get_item(user_id, item_id)

        if not item:
            await bot.send_message(
                call.message.chat.id,
                "❌ Item not found.",
            )
            return

        caption = item["caption"] or ""

        if item["item_type"] == "note":
            await bot.send_message(
                call.message.chat.id,
                f"📝 <b>Note #{item['id']}</b>\n\n{caption}",
                parse_mode="HTML",
                reply_markup=item_keyboard(item_id, subject_id),
            )

        elif item["item_type"] == "photo":
            await bot.send_photo(
                call.message.chat.id,
                item["file_id"],
                caption=caption or None,
                reply_markup=item_keyboard(item_id, subject_id),
            )

        elif item["item_type"] == "file":
            await bot.send_document(
                call.message.chat.id,
                item["file_id"],
                caption=caption or None,
                reply_markup=item_keyboard(item_id, subject_id),
            )
        return

    # -------------------------
    # Delete item
    # -------------------------
    if data.startswith("delete:"):
        _, item_id_str, subject_id_str = data.split(":")
        item_id = int(item_id_str)
        subject_id = int(subject_id_str)

        item = get_item(user_id, item_id)

        if not item:
            await bot.send_message(
                call.message.chat.id,
                "❌ Item not found.",
            )
            return

        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton(
                "✅ Yes, delete",
                callback_data=f"confirmdelete:{item_id}:{subject_id}",
            ),
            types.InlineKeyboardButton(
                "❌ Cancel",
                callback_data=f"view:{item_id}:{subject_id}",
            ),
        )

        await bot.send_message(
            call.message.chat.id,
            f"⚠️ Delete item <b>#{item_id}</b>?",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # -------------------------
    # Confirm delete
    # -------------------------
    if data.startswith("confirmdelete:"):
        _, item_id_str, subject_id_str = data.split(":")
        item_id = int(item_id_str)
        subject_id = int(subject_id_str)

        item = get_item(user_id, int(item_id_str))

        if not item:
            await bot.send_message(
                call.message.chat.id,
                "❌ Item already deleted or not found.",
            )
            return

        delete_item(user_id, int(item_id_str))

        await bot.send_message(
            call.message.chat.id,
            f"✅ Item #{item_id} deleted.",
            reply_markup=subject_keyboard(subject_id),
        )
        return


# ============================================================
# /CANCEL
# ============================================================

@bot.message_handler(commands=["cancel"])
async def cancel(message):
    user_id = message.from_user.id
    clear_state(user_id)

    await bot.send_message(
        message.chat.id,
        "❌ Cancelled.",
        reply_markup=subjects_keyboard(user_id),
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "document",
    ]
)
async def handle_message(message):
    user_id = message.from_user.id
    init_user(user_id)

    current = state.get(user_id)

    if not current:
        await bot.send_message(
            message.chat.id,
            "Please use /start to open your Study Assistant.",
        )
        return

    action = current["action"]
    subject_id = current["subject_id"]

    # -------------------------
    # Rename subject
    # -------------------------
    if action == "rename_subject":
        if not message.text:
            await bot.send_message(
                message.chat.id,
                "❌ Please send the new subject name as text.",
            )
            return

        new_name = message.text.strip()

        if not new_name:
            await bot.send_message(
                message.chat.id,
                "❌ Subject name cannot be empty.",
            )
            return

        if len(new_name) > 50:
            await bot.send_message(
                message.chat.id,
                "❌ Subject name is too long. Maximum 50 characters.",
            )
            return

        rename_subject(user_id, subject_id, new_name)
        clear_state(user_id)

        await bot.send_message(
            message.chat.id,
            f"✅ Subject {subject_id} renamed to <b>{new_name}</b>.",
            parse_mode="HTML",
            reply_markup=subject_keyboard(subject_id),
        )
        return

    # -------------------------
    # Add note
    # -------------------------
    if action == "add_note":
        if not message.text:
            await bot.send_message(
                message.chat.id,
                "❌ Please send your note as text.",
            )
            return

        note = message.text.strip()

        if not note:
            return

        item_id = add_item(
            user_id,
            subject_id,
            "note",
            None,
            note,
        )

        clear_state(user_id)

        await bot.send_message(
            message.chat.id,
            f"✅ Note saved as <b>#{item_id}</b>.",
            parse_mode="HTML",
            reply_markup=subject_keyboard(subject_id),
        )
        return

    # -------------------------
    # Add photo
    # -------------------------
    if action == "add_photo":
        if not message.photo:
            await bot.send_message(
                message.chat.id,
                "❌ Please send a photo.",
            )
            return

        photo = message.photo[-1]
        caption = message.caption or ""

        item_id = add_item(
            user_id,
            subject_id,
            "photo",
            photo.file_id,
            caption,
        )

        clear_state(user_id)

        await bot.send_message(
            message.chat.id,
            f"✅ Photo saved as <b>#{item_id}</b>.",
            parse_mode="HTML",
            reply_markup=subject_keyboard(subject_id),
        )
        return

    # -------------------------
    # Add file
    # -------------------------
    if action == "add_file":
        if not message.document:
            await bot.send_message(
                message.chat.id,
                "❌ Please send a document/file.",
            )
            return

        document = message.document
        caption = message.caption or document.file_name or ""

        item_id = add_item(
            user_id,
            subject_id,
            "file",
            document.file_id,
            caption,
        )

        clear_state(user_id)

        await bot.send_message(
            message.chat.id,
            f"✅ File saved as <b>#{item_id}</b>.",
            parse_mode="HTML",
            reply_markup=subject_keyboard(subject_id),
        )
        return


# ============================================================
# MAIN
# ============================================================

async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not configured. "
            "Set the BOT_TOKEN environment variable in Railway."
        )

    print("Study Assistant Bot is running...")
    await bot.infinity_polling(
        skip_pending=True,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    asyncio.run(main())
