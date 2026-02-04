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
        with open("bad_history.txt", "r", encoding="utf-8") as f:
            return f.read()
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
    st.header("Настройки")
    
    # Получаем ключ строго из секретов
    api_key_val = st.secrets.get("OPENROUTER_API_KEY")
    
    if not api_key_val:
        st.error("❌ Ошибка: Ключ OPENROUTER_API_KEY не найден в Secrets!")
        st.stop()
    else:
        st.success("✅ API-ключ подключен")
        
    selected_model = "google/gemini-2.5-flash"
    st.info(f"Модель: {selected_model}")

col1, col2 = st.columns(2)

with col1:
    contract_file = st.file_uploader("📄 Загрузите КОНТРАКТ (PDF/DOCX)", type=['pdf', 'docx'], key="contract_stable")
    if contract_file:
        st.info(f"📁 Файл: {contract_file.name}")

with col2:
    report_file = st.file_uploader("📝 Загрузите ЧЕРНОВИК ОТЧЕТА (PDF/DOCX)", type=['pdf', 'docx'], key="report_stable")
    if report_file:
        st.info(f"📝 Файл: {report_file.name}")

# --- ЛОГИКА АНАЛИЗА ---
if st.button("🚀 ЗАПУСТИТЬ ТОТАЛЬНЫЙ АУДИТ"):
    bad_history = load_bad_history() 
    if contract_file and report_file:
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key_val, 
            )

            progress_bar = st.progress(0)
            status = st.empty()

            # 1. Чтение файлов
            status.info("📂 Шаг 1/4: Чтение и индексация документов...")
            c_text = extract_text_from_pdf(contract_file) if contract_file.name.endswith('.pdf') else extract_text_from_docx(contract_file)
            r_text = extract_text_from_pdf(report_file) if report_file.name.endswith('.pdf') else extract_text_from_docx(report_file)
            
            progress_bar.progress(25)

            # 2. Подготовка промпта
            status.info("⚖️ Шаг 2/4: Сверка юридических условий и ТЗ...")
            system_prompt = f"""
            Ты — самый придирчивый инспектор госконтрактов. Проведи аудит по ТРЕМ СЛОЯМ:
            СЛОЙ 1: БАЗА ПРОШЛЫХ ОТКАЗОВ. Сверь отчет с этими историческими ошибками:
            {bad_history}
            СЛОЙ 2: ЭКСПЕРТНАЯ ЛОГИКА. Сверь требования Контракта с Отчетом. Найди нестыковки в ТЗ.
            СЛОЙ 3: ЛИНГВИСТИКА. Найди слова "около", "примерно", ошибки в "Российская Федерация".
            Ответ выдай строго по этим трем блокам с заголовками.
            """
            
            user_content = f"ТРЕБОВАНИЯ КОНТРАКТА:\n{c_text[:12000]}\n\nФАКТИЧЕСКИЙ ОТЧЕТ:\n{r_text[:12000]}"
            progress_bar.progress(50)

            # 3. Запрос к ИИ
            status.info("🧠 Шаг 3/4: Искусственный интеллект проводит аудит...")
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=3000,
                temperature=0.1  # <--- ДОБАВЛЕНО: Минимальная "фантазия", максимум точности
            )
            
            result_text = response.choices[0].message.content
            progress_bar.progress(85)

            # 4. Вывод результата
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
        st.warning("⚠️ Пожалуйста, загрузите оба файла для начала сравнения.")
