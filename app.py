import os
import streamlit as st
from openai import OpenAI
from docx import Document
from io import BytesIO
import fitz  # PyMuPDF
import time

# --- НАСТРОЙКА СТРАНИЦЫ ---
st.set_page_config(page_title="Симулятор Вредного Заказчика", layout="wide", page_icon="🧛")

# --- ФУНКЦИИ ЧТЕНИЯ ФАЙЛОВ ---
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for i, page in enumerate(doc):
        text += f"\n[СТРАНИЦА {i+1}]\n{page.get_text()}"
    return text

def extract_text_from_docx(file):
    doc = Document(file)
    text = ""
    for i, para in enumerate(doc.paragraphs):
        if para.text.strip():
            text += f"[Абзац {i+1}] {para.text}\n"
    return text

def load_bad_history():
    if os.path.exists("bad_history.txt"):
        try:
            with open("bad_history.txt", "r", encoding="utf-8") as f:
                return f.read()
        except:
            return "База прошлых отказов пуста."
    return "База прошлых отказов пуста."

def create_docx(text):
    doc = Document()
    doc.add_heading('ПРОТОКОЛ НЕСООТВЕТСТВИЙ', 0)
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- ИНТЕРФЕЙС ---
st.title("🧛 Симулятор Вредного Заказчика")
st.markdown("### Автоматизированный аудит соответствия Отчета и Контракта")

with st.sidebar:
    st.header("Настройки AI")
    model_option = st.selectbox(
        "Выберите модель DeepSeek:",
        ("deepseek-chat", "deepseek-reasoner"),
        index=0,
        help="chat — быстрая (V3), reasoner — умная (R1)"
    )
    selected_model = model_option

col1, col2 = st.columns(2)

with col1:
    contract_file = st.file_uploader("📄 Загрузите КОНТРАКТ (PDF/DOCX)", type=['pdf', 'docx'], key="c_stable")

with col2:
    report_file = st.file_uploader("📝 Загрузите ЧЕРНОВИК ОТЧЕТА (PDF/DOCX)", type=['pdf', 'docx'], key="r_stable")

# --- ЛОГИКА АНАЛИЗА ---
if st.button("🚀 ЗАПУСТИТЬ ТОТАЛЬНЫЙ АУДИТ"):
    if contract_file and report_file:
        try:
            # 1. Сначала достаем ключи и настройки
            api_key_val = st.secrets.get("DEEPSEEK_API_KEY")
            if not api_key_val:
                st.error("Ключ DEEPSEEK_API_KEY не найден в Secrets!")
                st.stop()
            
            bad_history = load_bad_history()
            
            # 2. Инициализация клиента
            client = OpenAI(
                base_url="https://api.deepseek.com",
                api_key=api_key_val, 
            )

            progress_bar = st.progress(0)
            status = st.empty()

            # Шаг 1: Чтение файлов
            status.info("📂 Шаг 1/4: Чтение и индексация документов...")
            c_text = extract_text_from_pdf(contract_file) if contract_file.name.endswith('.pdf') else extract_text_from_docx(contract_file)
            r_text = extract_text_from_pdf(report_file) if report_file.name.endswith('.pdf') else extract_text_from_docx(report_file)
            progress_bar.progress(25)

            # Шаг 2: Промпт
            status.info("⚖️ Шаг 2/4: Сверка юридических условий и ТЗ...")
            system_prompt = f"""
            Ты — ведущий аудитор Счетной палаты. Твоя задача: найти несоответствия в Отчете относительно Контракта.
            
            ### ТРЕБОВАНИЕ К ФОРМАТУ ОТВЕТА:
            Для КАЖДОЙ найденной ошибки ты ОБЯЗАН указывать точное местоположение в документе.
            Используй формат:
            [ЛОКАЦИЯ]: Страница №, Абзац №, (если есть: Глава/Пункт).
            
            ### ТРИ СЛОЯ ПРОВЕРКИ:
            1. ИСТОРИЧЕСКИЙ ОПЫТ (База отказов): {bad_history}
            2. ТЕХНИЧЕСКОЕ ЗАДАНИЕ: Сверка цифр, дат, объемов и фактов.
            3. ФОРМАЛИЗМ: Названия ведомств, ИНК, стоп-слова ("не менее", "около"), наличие печатей.
            
            ### ПРИМЕР ЗАПИСИ:
            - **Нарушение**: Неверный номер контракта.
            - **Локация**: Отчет, Страница 1, Абзац 3 (Титульный лист).
            - **Суть**: В контракте №35, в отчете указан №39.
            - **Риск**: Непринятие отчета из-за несоответствия первичным данным.
            """
            
            # Увеличиваем точность, передавая маркеры
            user_content = f"""
            ВНИМАНИЕ: В текстах ниже маркеры [СТРАНИЦА X] и [Абзац Y] проставлены для твоей навигации. 
            Используй их при цитировании локации ошибки.
            
            ТЕКСТ КОНТРАКТА:
            {c_text[:10000]}
            
            ТЕКСТ ОТЧЕТА:
            {r_text[:10000]}
            """
            
            user_content = f"ТРЕБОВАНИЯ КОНТРАКТА:\n{c_text[:10000]}\n\nФАКТИЧЕСКИЙ ОТЧЕТ:\n{r_text[:10000]}"
            progress_bar.progress(50)

            # Шаг 3: Запрос к ИИ
            status.info("🧠 Шаг 3/4: DeepSeek проводит аудит...")
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content
            progress_bar.progress(85)

            # Шаг 4: Вывод
            status.success("✅ Аудит успешно завершен!")
            progress_bar.progress(100)
            
            st.divider()
            st.subheader("📋 Протокол выявленных несоответствий")
            st.markdown(result_text)

            st.download_button(
                label="📥 Скачать протокол в Word",
                data=create_docx(result_text),
                file_name="Audit_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as e:
            st.error(f"⚠️ Произошла ошибка: {str(e)}")
    else:
        st.warning("⚠️ Пожалуйста, загрузите оба файла.")

