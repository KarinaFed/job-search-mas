"""Telegram bot for Job Search MAS."""
import asyncio
import io
from typing import Optional
import httpx
from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from loguru import logger
import os
from config import settings

# Conversation states
WAITING_FOR_RESUME = 1


class JobSearchBot:
    """Telegram bot for job search system."""
    
    def __init__(self, token: str, api_url: str = "http://localhost:8000"):
        """Initialize bot."""
        self.token = token
        self.api_url = api_url
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup command and message handlers."""
        # Start command
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Conversation handler for resume upload
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("upload", self.upload_command)],
            states={
                WAITING_FOR_RESUME: [
                    MessageHandler(filters.Document.PDF | filters.Document.ALL, self.handle_pdf),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_resume),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )
        self.application.add_handler(conv_handler)
        
        # Handle PDF files directly
        self.application.add_handler(MessageHandler(filters.Document.PDF, self.handle_pdf_direct))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = (
            "👋 Привет! Я помогу тебе найти работу.\n\n"
            "📋 Что я умею:\n"
            "✅ Анализировать твой профиль\n"
            "✅ Находить релевантные вакансии\n"
            "✅ Создавать готовые материалы для подачи\n\n"
            "🚀 Начнем? Отправь мне свое резюме:\n"
            "• В формате PDF (просто отправь файл)\n"
            "• Или текст резюме (команда /upload)\n\n"
            "Используй /help для списка команд."
        )
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "📚 Доступные команды:\n\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n"
            "/upload - Загрузить резюме (PDF или текст)\n"
            "/cancel - Отменить текущую операцию\n\n"
            "💡 Совет: Просто отправь PDF файл с резюме, и я начну обработку!"
        )
        await update.message.reply_text(help_text)
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upload command."""
        message = (
            "📤 Загрузи свое резюме:\n\n"
            "• Отправь PDF файл\n"
            "• Или отправь текст резюме\n\n"
            "Я обработаю его и найду для тебя подходящие вакансии!"
        )
        await update.message.reply_text(message)
        return WAITING_FOR_RESUME
    
    async def handle_pdf_direct(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF file sent directly (not in conversation)."""
        await self._process_pdf(update, context)
    
    async def handle_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF file in conversation."""
        await self._process_pdf(update, context)
        return ConversationHandler.END
    
    async def handle_text_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text resume in conversation."""
        resume_text = update.message.text
        
        if len(resume_text) < 50:
            await update.message.reply_text(
                "❌ Текст резюме слишком короткий. Пожалуйста, отправь полное резюме."
            )
            return WAITING_FOR_RESUME
        
        await self._process_text_resume(update, context, resume_text)
        return ConversationHandler.END
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation."""
        await update.message.reply_text("❌ Операция отменена.")
        return ConversationHandler.END
    
    async def _process_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process PDF file."""
        document: Document = update.message.document
        
        if not document.file_name.endswith('.pdf'):
            await update.message.reply_text("❌ Поддерживаются только PDF файлы.")
            return
        
        # Get user ID from Telegram
        telegram_id = str(update.effective_user.id)
        user_id = f"tg_{telegram_id}"
        
        # Download PDF
        status_msg = await update.message.reply_text("📥 Загружаю файл...")
        
        try:
            file = await context.bot.get_file(document.file_id)
            pdf_bytes = io.BytesIO()
            await file.download_to_memory(pdf_bytes)
            pdf_bytes.seek(0)
            
            await status_msg.edit_text("⏳ Обрабатываю резюме...\nЭто может занять до 25 минут, пожалуйста, подождите...")
            
            # Call API
            logger.info(f"Calling API: {self.api_url}/api/resume/full-journey")
            # Increase timeout to 25 minutes (1500 seconds) for full journey processing
            async with httpx.AsyncClient(timeout=1500.0) as client:
                files = {"file": (document.file_name, pdf_bytes.getvalue(), "application/pdf")}
                data = {"user_id": user_id}
                
                try:
                    response = await client.post(
                        f"{self.api_url}/api/resume/full-journey",
                        files=files,
                        data=data
                    )
                    logger.info(f"API response status: {response.status_code}")
                except httpx.ConnectError as e:
                    logger.error(f"Connection error to API {self.api_url}: {e}")
                    await status_msg.edit_text(
                        f"❌ Не удалось подключиться к серверу обработки.\n"
                        f"Проверьте, что API запущен на {self.api_url}"
                    )
                    return
                except httpx.TimeoutException as e:
                    logger.error(f"Timeout waiting for API response: {e}")
                    await status_msg.edit_text(
                        "❌ Превышено время ожидания ответа от сервера.\n"
                        "Обработка резюме занимает слишком много времени."
                    )
                    return
                except Exception as e:
                    logger.error(f"HTTP request error: {e}")
                    raise
            
            if response.status_code != 200:
                try:
                    error_text = response.json().get("detail", f"HTTP {response.status_code}: {response.text[:200]}")
                except:
                    error_text = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"API returned error: {error_text}")
                await status_msg.edit_text(f"❌ Ошибка обработки: {error_text}")
                return
            
            try:
                result = response.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {e}\nResponse text: {response.text[:500]}")
                await status_msg.edit_text("❌ Ошибка: не удалось обработать ответ сервера.")
                return
            
            await self._send_results(update, context, result, user_id, status_msg)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error processing PDF: {e}\nFull traceback:\n{error_details}")
            error_msg = f"❌ Произошла ошибка при обработке:\n{str(e)}"
            if len(error_msg) > 4096:
                error_msg = error_msg[:4090] + "..."
            try:
                await status_msg.edit_text(error_msg)
            except:
                await update.message.reply_text(error_msg)
    
    async def _process_text_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE, resume_text: str):
        """Process text resume."""
        telegram_id = str(update.effective_user.id)
        user_id = f"tg_{telegram_id}"
        
        status_msg = await update.message.reply_text("⏳ Обрабатываю резюме...\nЭто может занять до 25 минут, пожалуйста, подождите...")
        
        try:
            async with httpx.AsyncClient(timeout=1500.0) as client:
                data = {
                    "user_id": user_id,
                    "resume_text": resume_text
                }
                
                response = await client.post(
                    f"{self.api_url}/api/resume/full-journey",
                    data=data
                )
            
            if response.status_code != 200:
                error_text = response.json().get("detail", "Ошибка обработки")
                await status_msg.edit_text(f"❌ Ошибка: {error_text}")
                return
            
            result = response.json()
            await self._send_results(update, context, result, user_id, status_msg)
            
        except Exception as e:
            logger.error(f"Error processing text resume: {e}")
            await status_msg.edit_text(f"❌ Произошла ошибка при обработке: {str(e)}")
    
    async def _send_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          result: dict, user_id: str, status_msg):
        """Send processing results to user."""
        if result.get("status") != "completed":
            error = result.get("error", "Неизвестная ошибка")
            await status_msg.edit_text(f"❌ Обработка не завершена: {error}")
            return
        
        result_data = result.get("result", {})
        
        # Send profile analysis
        profile_analysis = result_data.get("profile_analysis", {})
        if profile_analysis:
            profile = profile_analysis.get("result", {}).get("profile", {})
            if profile:
                skills = profile.get("skills", [])
                skills_text = ", ".join([s.get("name", "") for s in skills[:5]])
                
                profile_msg = (
                    f"✅ Профиль проанализирован!\n\n"
                    f"📊 Уровень: {profile.get('seniority', 'N/A')}\n"
                    f"📍 Локация: {profile.get('location', 'N/A')}\n"
                    f"💼 Навыки: {skills_text}..."
                )
                await status_msg.edit_text(profile_msg)
        
        # Send job search results
        job_search = result_data.get("job_search", {})
        logger.info(f"Job search data received: {bool(job_search)}, keys: {list(job_search.keys()) if job_search else []}")
        
        if job_search:
            # Check if job_search has status field (it's a wrapped result)
            if job_search.get("status") == "completed":
                jobs_data = job_search.get("result", {})
            else:
                # If job_search is the result itself
                jobs_data = job_search if job_search else {}
            
            jobs = jobs_data.get("jobs", [])
            total = jobs_data.get("total_found", 0) or len(jobs)
            
            logger.info(f"Jobs extracted: {len(jobs)}, total_found: {total}")
            
            if not jobs or len(jobs) == 0:
                await update.message.reply_text(
                    "⚠️ Вакансии не найдены или данные не были переданы корректно."
                )
                logger.warning(f"No jobs found in job_search. Jobs data keys: {list(jobs_data.keys())}")
            else:
                # Send header message
                await update.message.reply_text(
                    f"📋 Найдено {total} релевантных вакансий!\n\n"
                    "Вот все подходящие вакансии (отсортированы по релевантности):",
                    disable_web_page_preview=True
                )
                
                # Send jobs in batches to avoid message length limit (4096 chars)
                # Telegram limit is 4096 chars, so we'll send ~8-10 jobs per message
                jobs_per_message = 8
                for batch_start in range(0, len(jobs), jobs_per_message):
                    batch = jobs[batch_start:batch_start + jobs_per_message]
                    jobs_msg = ""
                    
                    for i, job_match in enumerate(batch, batch_start + 1):
                        # Handle both dict and object formats
                        if isinstance(job_match, dict):
                            job = job_match.get("job", {})
                            score = job_match.get("relevance_score", 0)
                        else:
                            # JobMatch object
                            job = job_match.job.dict() if hasattr(job_match.job, 'dict') else {}
                            score = getattr(job_match, 'relevance_score', 0)
                        
                        title = job.get('title', 'N/A') if isinstance(job, dict) else getattr(job, 'title', 'N/A')
                        company = job.get('company', 'N/A') if isinstance(job, dict) else getattr(job, 'company', 'N/A')
                        url = job.get('url', '') if isinstance(job, dict) else getattr(job, 'url', '')
                        
                        if not url:
                            logger.warning(f"Job {i} has no URL: {title}")
                        
                        jobs_msg += (
                            f"{i}. {title}\n"
                            f"   🏢 {company}\n"
                            f"   ⭐ Релевантность: {score:.0%}\n"
                            f"   🔗 {url}\n\n"
                        )
                    
                    # Send batch if not empty
                    if jobs_msg:
                        try:
                            await update.message.reply_text(jobs_msg, disable_web_page_preview=True)
                            await asyncio.sleep(0.3)  # Small delay between messages to avoid rate limiting
                            logger.info(f"Sent batch {batch_start // jobs_per_message + 1} with {len(batch)} jobs")
                        except Exception as e:
                            logger.error(f"Error sending jobs batch: {e}")
                            await update.message.reply_text(f"Ошибка при отправке вакансий: {str(e)}")
        else:
            logger.warning("No job_search data in result")
            await update.message.reply_text("⚠️ Данные о вакансиях не были получены.")
        
        # Send applications
        applications = result_data.get("applications", [])
        if applications:
            apps_msg = f"📧 Готовы материалы для {len(applications)} лучших вакансий:\n\n"
            await update.message.reply_text(apps_msg)
            
            for i, app in enumerate(applications, 1):
                job_title = app.get("job_title", "N/A")
                company = app.get("company", "N/A")
                
                # Handle nested structure: application.result.application or application.application
                application_result = app.get("application", {})
                if isinstance(application_result, dict):
                    # Try both possible structures
                    application_data = application_result.get("application", application_result)
                else:
                    application_data = {}
                
                if application_data:
                    cover_letter = application_data.get("cover_letter", "")
                    adapted_resume = application_data.get("adapted_resume", "")
                    
                    header = f"{i}. {job_title} - {company}\n\n"
                    
                    # Send cover letter if available
                    if cover_letter and cover_letter.strip():
                        try:
                            letter_file = io.BytesIO(cover_letter.encode('utf-8'))
                            letter_file.name = f"Письмо_{company}_{i}.txt"
                            await update.message.reply_document(
                                document=letter_file,
                                caption=f"{header}📄 Сопроводительное письмо"
                            )
                            logger.info(f"Sent cover letter for {company}")
                        except Exception as e:
                            logger.error(f"Error sending cover letter: {e}")
                    else:
                        logger.warning(f"No cover letter found for {company}")
                    
                    # Send resume if available
                    if adapted_resume and adapted_resume.strip():
                        try:
                            resume_file = io.BytesIO(adapted_resume.encode('utf-8'))
                            resume_file.name = f"Резюме_{company}_{i}.txt"
                            await update.message.reply_document(
                                document=resume_file,
                                caption=f"{header}📄 Адаптированное резюме"
                            )
                            logger.info(f"Sent adapted resume for {company}")
                        except Exception as e:
                            logger.error(f"Error sending resume: {e}")
                    else:
                        logger.warning(f"No adapted resume found for {company}")
                    
                    await asyncio.sleep(0.5)  # Rate limiting
                else:
                    logger.warning(f"No application data found for {company}")
        
        final_msg = (
            "\n✅ Готово! Все материалы готовы к отправке работодателям.\n\n"
            "💡 Совет: Скопируй письма и резюме из файлов выше и отправь их на вакансии.\n\n"
            "Используй /upload для загрузки нового резюме."
        )
        await update.message.reply_text(final_msg)
    
    def run(self):
        """Run the bot."""
        logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point."""
    # Try to get token from settings first, then from environment
    token = settings.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")
        logger.error("Please set TELEGRAM_BOT_TOKEN in .env file or environment variable")
        return
    
    api_url = os.getenv("API_URL", "http://api:8000")
    
    bot = JobSearchBot(token=token, api_url=api_url)
    bot.run()


if __name__ == "__main__":
    main()

