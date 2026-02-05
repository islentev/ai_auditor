import os
import streamlit as st
from openai import OpenAI
from docx import Document
from io import BytesIO
import fitz  # PyMuPDF

# --- НАСТРОЙКА ---
st.set_page_config(page_title="Аудитор 🧛", layout="wide", page_icon="🧛")

def extract_text(file):
    """Извлекает текст из PDF или DOCX."""
    try:
        if file.name.endswith('.pdf'):
            doc = fitz.open(stream=file.read(), filetype="pdf")
            text = "".join([f"\n[СТРАНИЦА {i+1}]\n{p.get_text()}" for i, p in enumerate(doc)])
            return text
        else:
            doc = Document(file)
            text = "".join([f"[Абзац {i+1}] {p.text}\n" for i, p in enumerate(doc.paragraphs) if p.text.strip()])
            return text
    except Exception as e:
        st.error(f"Ошибка чтения файла {file.name}: {e}")
        return ""

def create_docx(text):
    """Создает Word-файл из текста."""
    doc = Document()
    doc.add_heading('ПРОТОКОЛ НЕСООТВЕТСТВИЙ', 0)
    for line in text.split('\n'):
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# --- ИНТЕРФЕЙС ---
with st.sidebar:
    st.header("⚙️ Настройки")
    selected_model = st.selectbox(
        "Выберите модель:", 
        ("deepseek-chat", "deepseek-reasoner"),
        help="Chat — быстрая. Reasoner (R1) — думает над сложной логикой."
    )
    st.divider()
    st.caption("Если Reasoner долго думает — это нормально, он строит цепочку рассуждений.")

st.title("🧛 Симулятор Вредного Заказчика")
st.markdown("### Сверка Отчета с требованиями Контракта")

col1, col2 = st.columns(2)
with col1:
    contract_file = st.file_uploader("📄 Загрузите КОНТРАКТ", type=['pdf', 'docx'])
with col2:
    report_file = st.file_uploader("📝 Загрузите ОТЧЕТ", type=['pdf', 'docx'])

if st.button("🚀 ЗАПУСТИТЬ ТОТАЛЬНЫЙ АУДИТ"):
    if contract_file and report_file:
        try:
            # 1. Секреты и инициализация
            api_key = st.secrets.get("DEEPSEEK_API_KEY")
            if not api_key:
                st.error("Ошибка: Введите DEEPSEEK_API_KEY в Secrets!")
                st.stop()
                
            client = OpenAI(base_url="https://api.deepseek.com", api_key=api_key)
            
            # 2. Чтение файлов
            with st.status("📁 Обработка документов...", expanded=True) as status:
                c_text = extract_text(contract_file)
                r_text = extract_text(report_file)
                
                if not c_text or not r_text:
                    st.error("❌ Файлы пустые или не распознаны.")
                    st.stop()
                
                status.update(label="🧠 ИИ анализирует данные...", state="running")

                # 3. Подготовка запроса
                sys_msg = """Ты профессиональный аудитор. Твоя задача: найти несоответствия в Отчете, сверяя его с Контрактом.
                Для каждой ошибки СТРОГО указывай:
                1. Нарушение
                2. Локация: (Страница №, Абзац № из текста)
                3. Суть и Риск.
                Если нарушений нет, так и напиши."""

                usr_msg = f"""Используй маркеры [СТРАНИЦА] и [Абзац] для указания локации.
                
                КОНТРАКТ:
                {c_text[:12000]}
                
                ОТЧЕТ:
                {r_text[:12000]}"""

                # Настройка параметров (для Reasoner убираем temperature)
                params = {
                    "model": selected_model,
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": usr_msg}
                    ],
                    "max_tokens": 4000
                }
                
                if selected_model == "deepseek-chat":
                    params["temperature"] = 0.1

                # 4. Выполнение запроса
                res = client.chat.completions.create(**params)
                
                # Логика извлечения контента
                reasoning = getattr(res.choices[0].message, 'reasoning_content', None)
                report_content = res.choices[0].message.content
                
                status.update(label="✅ Анализ завершен!", state="complete", expanded=False)

            # 5. Вывод результатов
            if reasoning:
                with st.expander("🔍 Посмотреть ход мыслей ИИ (Reasoning)"):
                    st.info(reasoning)

            if report_content:
                st.subheader("📋 Итоговый протокол несоответствий")
                st.markdown(report_content)
                
                st.download_button(
                    label="📥 Скачать протокол в Word",
                    data=create_docx(report_content),
                    file_name="Audit_Report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            elif reasoning:
                st.warning("ИИ выдал только размышления без финального текста. Посмотрите их в блоке выше.")
            else:
                st.error("⚠️ Модель вернула пустой ответ. Попробуйте еще раз или смените модель.")

        except Exception as e:
            st.error(f"❌ Ошибка API или системы: {str(e)}")
    else:
        st.warning("⚠️ Пожалуйста, загрузите оба файла.")
