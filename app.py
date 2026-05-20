import streamlit as st
from openai import OpenAI
import re
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import io

import urllib.request
import matplotlib.font_manager as fm
try:
    urllib.request.urlretrieve(
        "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
        "/tmp/NotoSansCJK.otf"
    )
    fm.fontManager.addfont("/tmp/NotoSansCJK.otf")
    prop = fm.FontProperties(fname="/tmp/NotoSansCJK.otf")
    matplotlib.rcParams['font.family'] = prop.get_name()
except:
    pass
matplotlib.rcParams['axes.unicode_minus'] = False

try:
    import opencc
    converter = opencc.OpenCC('t2s')
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False

def to_simplified(text):
    if HAS_OPENCC:
        return converter.convert(text)
    return text

def safe_text(text):
    return text.encode('utf-8', errors='replace').decode('utf-8')

def clean_text(text, book_name=""):
    text = re.sub(r'About this digital edition.*', '', text, flags=re.DOTALL)
    if book_name == "论语":
        text = re.sub(r'^.*?学而', '学而', text, flags=re.DOTALL)
    lines = text.split('\n')
    lines = [l for l in lines if not re.fullmatch(r'[\s\d/]+', l)]
    return '\n'.join(lines)

STOPWORDS = set(
    "的了是在有和与及也其所以而为则于此之乎者矣焉哉夫且若"
    "曰子不以无亦或则已何乃若此彼所将欲"
)

def tokenize(text):
    chars = re.findall(r'[\u4e00-\u9fff]', text)
    return [c for c in chars if c not in STOPWORDS]

def get_chapters(text, book_name="论语"):
    if book_name == "论语":
        names = ["学而", "为政", "八佾", "里仁", "公冶长",
                 "雍也", "述而", "泰伯", "子罕", "乡党",
                 "先进", "颜渊", "子路", "宪问", "卫灵公",
                 "季氏", "阳货", "微子", "子张", "尧曰"]
        return ["全部"] + names
    if book_name in ("大学", "中庸"):
        patterns = re.findall(r'第[一二三四五六七八九十百\d]+章', text)
        unique = list(dict.fromkeys(patterns))
        return ["全部"] + unique if unique else ["全部"]
    patterns = re.findall(r'[卷章篇][一二三四五六七八九十百]+|第[一二三四五六七八九十百\d]+[卷章篇]', text)
    unique = list(dict.fromkeys(patterns))
    return ["全部"] + unique[:30] if unique else ["全部"]

def filter_by_chapter(text, chapter):
    if chapter == "全部":
        return text
    lines = text.split('\n')
    filtered = [l for l in lines if chapter in l]
    return '\n'.join(filtered) if filtered else text

def word_freq_chart(text, top_n=20):
    tokens = tokenize(text)
    if not tokens:
        return None, None
    freq = Counter(tokens).most_common(top_n)
    words, counts = zip(*freq)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(list(reversed(words)), list(reversed(counts)), color='#8B6914')
    ax.set_xlabel("出现次数", fontsize=12)
    ax.set_title(f"高频字 Top {top_n}", fontsize=14)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    return fig, freq

def concept_compare(text, c1, c2):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    both  = [l for l in lines if c1 in l and c2 in l]
    only1 = [l for l in lines if c1 in l and c2 not in l]
    only2 = [l for l in lines if c2 in l and c1 not in l]
    return both, only1, only2

def df_to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()

def load_builtin(filename, book_name):
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()
        return clean_text(to_simplified(raw), book_name=book_name)
    except FileNotFoundError:
        return None

def clear_book_cache():
    st.session_state['messages'] = []
    for key in ['freq_fig', 'freq_data', 'freq_ai',
                 'compare_both', 'compare_only1', 'compare_only2',
                 'compare_c1', 'compare_c2', 'compare_ai']:
        st.session_state.pop(key, None)

# ── 页面设置 ──────────────────────────────────────────────

client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="古典文献智能研究助手", layout="wide")
st.title("📜 古典文献智能研究助手")
st.caption("支持任意古籍 · 词频分析 · 概念对比 · 多轮问答")

# ── 手机端文本选择 ──────────────────────────────────────────
st.info("📱 手机用户：点击下方按钮切换文本；电脑用户：使用左侧边栏", icon="ℹ️")
mobile_cols = st.columns(4)
book_options = ["论语", "大学", "中庸", "上传文本"]
if 'mobile_book' not in st.session_state:
    st.session_state['mobile_book'] = "论语"

for i, name in enumerate(book_options):
    with mobile_cols[i]:
        if st.button(name, use_container_width=True,
                     type="primary" if st.session_state['mobile_book'] == name else "secondary"):
            if st.session_state['mobile_book'] != name:
                st.session_state['mobile_book'] = name
                clear_book_cache()
                st.rerun()

st.divider()

if not HAS_OPENCC:
    st.warning("⚠️ 未检测到 opencc，繁简转换不可用。")

# ── 侧栏 ──────────────────────────────────────────────────

with st.sidebar:
    st.header("📂 文本设置")

    sidebar_options = ["论语", "大学", "中庸", "上传自定义文本"]
    default_idx = 0
    if st.session_state.get('mobile_book') in sidebar_options:
        default_idx = sidebar_options.index(st.session_state['mobile_book'])

    text_source = st.radio(
        "选择文本来源",
        sidebar_options,
        index=default_idx,
        key="sidebar_source"
    )

    if 'last_book' not in st.session_state:
        st.session_state['last_book'] = text_source
    if text_source != st.session_state['last_book']:
        st.session_state['last_book'] = text_source
        st.session_state['mobile_book'] = text_source
        clear_book_cache()

    if text_source == "论语":
        raw_text = load_builtin('lunyu.txt', '论语')
        book_name = "论语"
        if raw_text:
            st.success(f"已加载《论语》，共 {len(raw_text)} 字")
        else:
            st.error("未找到 lunyu.txt")
    elif text_source == "大学":
        raw_text = load_builtin('daxue.txt', '大学')
        book_name = "大学"
        if raw_text:
            st.success(f"已加载《大学》，共 {len(raw_text)} 字")
        else:
            st.error("未找到 daxue.txt")
    elif text_source == "中庸":
        raw_text = load_builtin('zhongyong.txt', '中庸')
        book_name = "中庸"
        if raw_text:
            st.success(f"已加载《中庸》，共 {len(raw_text)} 字")
        else:
            st.error("未找到 zhongyong.txt")
    else:
        uploaded = st.file_uploader("上传古籍 txt 文件", type=['txt'])
        if uploaded:
            raw = uploaded.read().decode('utf-8', errors='ignore')
            book_name = uploaded.name.replace('.txt', '')
            raw_text = clean_text(to_simplified(raw), book_name=book_name)
            st.success(f"已加载《{book_name}》，共 {len(raw_text)} 字")
        else:
            raw_text = None
            book_name = ""
            st.warning("请上传文本文件")

    if raw_text:
        st.subheader("📖 篇章筛选")
        chapters = get_chapters(raw_text, book_name)
        selected_chapter = st.selectbox("选择篇章", chapters)
        text_content = filter_by_chapter(raw_text, selected_chapter)
        if selected_chapter != "全部":
            line_count = len([l for l in text_content.split('\n') if l.strip()])
            st.info(f"{selected_chapter}，共 {line_count} 条")
    else:
        text_content = None

# ── 主区域 ────────────────────────────────────────────────

if text_content:
    tab1, tab2, tab3 = st.tabs(["💬 多轮问答", "📊 词频分析", "🔍 概念对比"])

    with tab1:
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("输入问题，AI结合原文作答"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            system_prompt = f"""你是一个专业的古典文献研究助手，正在分析《{book_name}》。
回答时请：
1. 结合以下原文内容，引用具体章句
2. 用现代学术语言解释，保持严谨性
3. 如原文无相关内容，请明确说明

古籍原文（节选）：
{safe_text(text_content[:4000])}
"""
            with st.chat_message("assistant"):
                with st.spinner("思考中…"):
                    response = client.chat.completions.create(
                        model="deepseek-v4-flash",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            *st.session_state.messages
                        ]
                    )
                    answer = response.choices[0].message.content
                    st.markdown(answer)

            st.session_state.messages.append({"role": "assistant", "content": answer})

        if st.session_state.get('messages'):
            if st.button("清空对话", key="clear"):
                st.session_state.messages = []
                st.rerun()

    with tab2:
        st.subheader(f"《{book_name}》词频分析")
        col1, col2 = st.columns([3, 1])
        with col2:
            top_n = st.slider("显示前 N 个高频字", 10, 40, 20)
            run_freq = st.button("生成词频图", type="primary")

        if run_freq:
            with st.spinner("分析中…"):
                fig, freq = word_freq_chart(text_content, top_n)
            st.session_state['freq_fig'] = fig
            st.session_state['freq_data'] = freq
            st.session_state.pop('freq_ai', None)

        if 'freq_data' in st.session_state and st.session_state['freq_data']:
            fig = st.session_state['freq_fig']
            freq = st.session_state['freq_data']

            with col1:
                st.pyplot(fig)
            st.subheader("频率数据表")
            df = pd.DataFrame(freq, columns=["字", "频次"])
            df["占比"] = (df["频次"] / df["频次"].sum() * 100).round(2).astype(str) + "%"
            st.dataframe(df, use_container_width=True, hide_index=True)

            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button("📥 下载 CSV", csv,
                    file_name=f"{book_name}_词频.csv", mime="text/csv")
            with col_xlsx:
                xlsx = df_to_excel(df)
                st.download_button("📥 下载 Excel", xlsx,
                    file_name=f"{book_name}_词频.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.divider()
            if st.button("📝 让AI解读这份词频数据"):
                top_words = "、".join([w for w, _ in freq[:10]])
                ai_prompt = (f"《{book_name}》中出现频率最高的10个字是：{top_words}。"
                             f"请从文献学和思想史角度分析这些高频字反映了什么核心主题？")
                with st.spinner("AI分析中…"):
                    resp = client.chat.completions.create(
                        model="deepseek-v4-flash",
                        messages=[
                            {"role": "system", "content": "你是古典文献学专家，擅长从词频数据解读文本的思想主题。"},
                            {"role": "user", "content": ai_prompt}
                        ]
                    )
                    st.session_state['freq_ai'] = resp.choices[0].message.content

            if 'freq_ai' in st.session_state:
                st.markdown(st.session_state['freq_ai'])

    with tab3:
        st.subheader("概念对比分析")
        if HAS_OPENCC:
            st.caption("✅ 已启用繁简转换，输入简体或繁体均可匹配")
        else:
            st.caption("⚠️ 未启用繁简转换，请按文本实际字体输入概念")

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            concept1 = st.text_input("概念一", placeholder="例如：仁")
        with col2:
            concept2 = st.text_input("概念二", placeholder="例如：礼")
        with col3:
            st.write("")
            st.write("")
            run_compare = st.button("开始对比", type="primary")

        # ✅ 点"开始对比"时把结果存入 session_state
        if run_compare and concept1 and concept2:
            c1 = to_simplified(concept1)
            c2 = to_simplified(concept2)
            both, only1, only2 = concept_compare(text_content, c1, c2)
            st.session_state['compare_c1'] = c1
            st.session_state['compare_c2'] = c2
            st.session_state['compare_both'] = both
            st.session_state['compare_only1'] = only1
            st.session_state['compare_only2'] = only2
            st.session_state.pop('compare_ai', None)

        # ✅ 从 session_state 读取并展示结果，下载和AI分析按钮不会丢失内容
        if 'compare_both' in st.session_state:
            c1 = st.session_state['compare_c1']
            c2 = st.session_state['compare_c2']
            both = st.session_state['compare_both']
            only1 = st.session_state['compare_only1']
            only2 = st.session_state['compare_only2']

            m1, m2, m3 = st.columns(3)
            m1.metric(f"「{c1}」+「{c2}」共现", f"{len(both)} 条")
            m2.metric(f"仅含「{c1}」", f"{len(only1)} 条")
            m3.metric(f"仅含「{c2}」", f"{len(only2)} 条")

            st.divider()

            if both:
                st.markdown(f"#### 共现章句（共 {len(both)} 条，展示前10）")
                for line in both[:10]:
                    highlighted = (line
                        .replace(c1, f"**:orange[{c1}]**")
                        .replace(c2, f"**:blue[{c2}]**"))
                    st.markdown(f"• {highlighted}")

                both_df = pd.DataFrame({"章句": both,
                    f"含「{c1}」": [c1 in l for l in both],
                    f"含「{c2}」": [c2 in l for l in both]})
                col_csv2, col_xlsx2 = st.columns(2)
                with col_csv2:
                    csv2 = both_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button("📥 下载共现章句 CSV", csv2,
                        file_name=f"{c1}_{c2}_共现.csv", mime="text/csv")
                with col_xlsx2:
                    xlsx2 = df_to_excel(both_df)
                    st.download_button("📥 下载共现章句 Excel", xlsx2,
                        file_name=f"{c1}_{c2}_共现.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info(f"未找到「{c1}」与「{c2}」同时出现的章句")

            st.divider()
            if st.button("🤖 AI深度分析两者关系"):
                context = ('\n'.join(both[:15]) if both
                    else f"仅含{c1}的句子：{'；'.join(only1[:5])}\n仅含{c2}的句子：{'；'.join(only2[:5])}")
                ai_prompt = f"""在《{book_name}》中，「{c1}」与「{c2}」的关系分析：

共现章句：
{safe_text(context)}

请分析：
1. 两者在原文中呈现何种关系（并列、递进、对立、从属）？
2. 各自的核心内涵是什么？
3. 从思想史角度，这两个概念的关系有何学术意义？"""
                with st.spinner("AI分析中…"):
                    resp = client.chat.completions.create(
                        model="deepseek-v4-flash",
                        messages=[
                            {"role": "system", "content": f"你是古典文献学专家，正在研究《{book_name}》中的核心概念。"},
                            {"role": "user", "content": ai_prompt}
                        ]
                    )
                    st.session_state['compare_ai'] = resp.choices[0].message.content

            # ✅ AI分析结果也从 session_state 读取，不会因下载按钮消失
            if 'compare_ai' in st.session_state:
                st.markdown(st.session_state['compare_ai'])

else:
    st.info("👈 请在左侧选择或上传文本文件开始使用")
