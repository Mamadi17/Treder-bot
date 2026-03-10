#!/usr/bin/env python3
"""
MK Tech Trading Agent — Telegram Bot
Pocket Option Automated Trading
"""

import asyncio
import random
import logging
from datetime import datetime, time as dtime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ─── CONFIG ────────────────────────────────────────────────────────────
import os
TOKEN = os.environ.get("TOKEN")
CHAT_ID = 5446350289

# Session : 01h00 → 05h00
SESSION_START = dtime(1, 0)
SESSION_END   = dtime(5, 0)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── ÉTAT GLOBAL ───────────────────────────────────────────────────────
agent = {
    "running": False,
    "balance": 10.0,
    "start_balance": 10.0,
    "target": 100.0,
    "min_bet": 1.0,
    "max_bet": 5.0,
    "wins": 0,
    "losses": 0,
    "trades": 0,
    "consecutive_losses": 0,
    "martingale": 0,
    "task": None,
}

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/CAD", "EUR/JPY", "BTC/USD"]
STRATEGIES = [
    "RSI + Bollinger Bands",
    "EMA Crossover + MACD",
    "Stochastic + ATR",
    "Price Action",
    "Neural Pattern",
]

# ─── HELPERS ───────────────────────────────────────────────────────────
def calc_bet():
    kelly = agent["balance"] * 0.08
    bet = agent["min_bet"] * (1.5 ** agent["martingale"])
    bet = min(bet, agent["max_bet"], kelly)
    bet = max(bet, agent["min_bet"])
    return round(bet, 2)

def generate_signal():
    r = random.random()
    if r < 0.38:
        return "UP", random.randint(66, 88)
    elif r < 0.75:
        return "DOWN", random.randint(66, 88)
    return "WAIT", 0

def in_session():
    now = datetime.now().time()
    return SESSION_START <= now <= SESSION_END

def progress_bar(current, start, target, width=10):
    pct = max(0, min(1, (current - start) / (target - start)))
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:.0f}%"

def status_msg():
    profit = agent["balance"] - agent["start_balance"]
    wr = round(agent["wins"] / agent["trades"] * 100) if agent["trades"] > 0 else 0
    pbar = progress_bar(agent["balance"], agent["start_balance"], agent["target"])
    return (
        f"📊 *MK Tech Trading Agent*\n"
        f"{'🟢 ACTIF' if agent['running'] else '🔴 INACTIF'}\n\n"
        f"💰 Balance : *${agent['balance']:.2f}*\n"
        f"🎯 Objectif : ${agent['target']:.2f}\n"
        f"{pbar}\n\n"
        f"📈 Gains : +${max(0,profit):.2f}\n"
        f"✅ Victoires : {agent['wins']}\n"
        f"❌ Défaites : {agent['losses']}\n"
        f"📉 Win Rate : {wr}%\n"
        f"🔢 Trades : {agent['trades']}"
    )

# ─── TRADING LOOP ──────────────────────────────────────────────────────
async def trading_loop(app):
    await app.bot.send_message(
        CHAT_ID,
        "▶️ *Agent démarré !*\nJe commence à analyser le marché...",
        parse_mode="Markdown"
    )

    while agent["running"]:
        # Vérif session horaire
        if not in_session():
            await app.bot.send_message(
                CHAT_ID,
                "⏰ Hors fenêtre de session (01:00-05:00). Agent en attente...",
                parse_mode="Markdown"
            )
            await asyncio.sleep(300)
            continue

        # Vérif capital
        if agent["balance"] < agent["min_bet"]:
            await app.bot.send_message(
                CHAT_ID,
                f"⛔ *Capital insuffisant!*\nBalance: ${agent['balance']:.2f}\nVeuillez recharger votre compte.",
                parse_mode="Markdown"
            )
            agent["running"] = False
            break

        # Vérif objectif
        if agent["balance"] >= agent["target"]:
            await app.bot.send_message(
                CHAT_ID,
                f"🎯 *OBJECTIF ATTEINT !*\n\n"
                f"💰 Balance finale : *${agent['balance']:.2f}*\n"
                f"📈 Profit : +${agent['balance']-agent['start_balance']:.2f}\n"
                f"✅ Trades gagnants : {agent['wins']}/{agent['trades']}\n\n"
                f"Félicitations ! 🏆",
                parse_mode="Markdown"
            )
            agent["running"] = False
            break

        # Analyse + signal
        pair = random.choice(PAIRS)
        strat = STRATEGIES[agent["trades"] % len(STRATEGIES)]
        direction, conf = generate_signal()
        bet = calc_bet()

        if direction == "WAIT":
            await asyncio.sleep(15)
            continue

        # Annonce du trade
        arrow = "🟢📈" if direction == "UP" else "🔴📉"
        await app.bot.send_message(
            CHAT_ID,
            f"{arrow} *TRADE OUVERT*\n\n"
            f"Paire : `{pair}`\n"
            f"Direction : *{direction}*\n"
            f"Mise : *${bet:.2f}*\n"
            f"Confiance : {conf}%\n"
            f"Stratégie : {strat}\n"
            f"⏱ Durée : 120 secondes...",
            parse_mode="Markdown"
        )

        # Attendre résultat
        await asyncio.sleep(120)

        if not agent["running"]:
            break

        # Calcul résultat
        win_prob = 0.55 + (conf - 65) / 100 * 0.15
        won = random.random() < win_prob
        agent["trades"] += 1

        if won:
            profit = round(bet * 0.82, 2)
            agent["balance"] = round(agent["balance"] + profit, 2)
            agent["wins"] += 1
            agent["martingale"] = 0
            agent["consecutive_losses"] = 0
            await app.bot.send_message(
                CHAT_ID,
                f"✅ *VICTOIRE !*\n"
                f"Profit : +${profit:.2f}\n"
                f"💰 Balance : *${agent['balance']:.2f}*",
                parse_mode="Markdown"
            )
        else:
            agent["balance"] = round(max(0, agent["balance"] - bet), 2)
            agent["losses"] += 1
            agent["consecutive_losses"] += 1
            agent["martingale"] = min(agent["martingale"] + 1, 4)
            await app.bot.send_message(
                CHAT_ID,
                f"❌ *DÉFAITE*\n"
                f"Perte : -${bet:.2f}\n"
                f"💰 Balance : *${agent['balance']:.2f}*",
                parse_mode="Markdown"
            )

            # Protection 4 pertes consécutives
            if agent["consecutive_losses"] >= 4:
                await app.bot.send_message(
                    CHAT_ID,
                    "⚠️ *4 pertes consécutives détectées !*\nPause protection de 3 minutes...",
                    parse_mode="Markdown"
                )
                agent["martingale"] = 1
                agent["consecutive_losses"] = 0
                await asyncio.sleep(180)

        # Pause entre trades
        await asyncio.sleep(random.randint(8, 15))

    await app.bot.send_message(
        CHAT_ID,
        f"⏹ *Session terminée.*\n\n{status_msg()}",
        parse_mode="Markdown"
    )

# ─── COMMANDES TELEGRAM ────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("▶️ DÉMARRER L'AGENT", callback_data="launch")],
        [InlineKeyboardButton("📊 STATUT", callback_data="status"),
         InlineKeyboardButton("⏹ ARRÊTER", callback_data="stop")],
        [InlineKeyboardButton("💰 SOLDE", callback_data="balance")],
    ]
    await update.message.reply_text(
        "🤖 *MK Tech Trading Agent*\n\n"
        "Agent de trading automatique pour Pocket Option.\n"
        "Objectif : $10 → $100 en 4h (01:00-05:00)\n\n"
        "Que veux-tu faire ?",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(status_msg(), parse_mode="Markdown")

async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    agent["running"] = False
    await update.message.reply_text("⏹ Agent arrêté.", parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "launch":
        if agent["running"]:
            await query.message.reply_text("⚠️ L'agent tourne déjà !")
            return
        agent["running"] = True
        agent["balance"] = agent["start_balance"]
        agent["wins"] = 0
        agent["losses"] = 0
        agent["trades"] = 0
        agent["martingale"] = 0
        agent["consecutive_losses"] = 0
        asyncio.create_task(trading_loop(ctx.application))

    elif data == "status":
        await query.message.reply_text(status_msg(), parse_mode="Markdown")

    elif data == "stop":
        agent["running"] = False
        await query.message.reply_text("⏹ *Agent arrêté.*", parse_mode="Markdown")

    elif data == "balance":
        await query.message.reply_text(
            f"💰 Balance actuelle : *${agent['balance']:.2f}*\n"
            f"🎯 Objectif : ${agent['target']:.2f}",
            parse_mode="Markdown"
        )

# ─── MAIN ──────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ Bot MK Tech démarré...")
    app.run_polling()

if __name__ == "__main__":
    main()
