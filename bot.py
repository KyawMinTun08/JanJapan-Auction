        def main():
    app = Application.builder().token(BOT_TOKEN).build()
    ...
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
အသစ် (ထည့်ပါ):
if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("find",    cmd_find))
    app.add_handler(CommandHandler("model",   cmd_model))
    app.add_handler(CommandHandler("price",   cmd_price))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("web",     cmd_web))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(btn_callback))
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
