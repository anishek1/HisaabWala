import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from config import settings
from services.rate_limiter import RateLimiter
from services.stats import stats_tracker
from telegram.webhook import is_duplicate, register_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("hisaabwala")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    limiter = RateLimiter(settings.RATE_LIMIT_PER_DAY)

    register_handlers(dp, limiter)
    app.state.bot = bot
    app.state.dp = dp
    app.state.rate_limiter = limiter

    if settings.ENVIRONMENT == "production" and settings.WEBHOOK_URL:
        try:
            await bot.set_webhook(
                url=settings.WEBHOOK_URL,
                secret_token=settings.WEBHOOK_SECRET,
            )
            logger.info("Webhook configured.", extra={"webhook_url": settings.WEBHOOK_URL})
        except Exception:
            logger.exception("Failed to configure webhook.")

    logger.info("HisaabWala bot started.")

    try:
        yield
    finally:
        current_task = asyncio.current_task()
        pending_tasks = [
            task
            for task in asyncio.all_tasks()
            if task is not current_task and not task.done()
        ]
        for task in pending_tasks:
            task.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

        await bot.session.close()
        logger.info("HisaabWala bot shutdown complete.")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "bot": "HisaabWala"}


@app.get("/metrics")
async def metrics() -> dict[str, int]:
    return stats_tracker.snapshot()


@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> Any:
    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        logger.warning("Webhook secret mismatch.")
        return JSONResponse(content={"ok": False}, status_code=403)

    bot: Bot = request.app.state.bot
    dp: Dispatcher = request.app.state.dp

    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})

        if update.message and await is_duplicate(update.message.message_id):
            return {"ok": True}

        await dp.feed_update(bot=bot, update=update)
        return {"ok": True}
    except Exception:
        logger.exception("Failed to process webhook update.")
        return {"ok": True}
