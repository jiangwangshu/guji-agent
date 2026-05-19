# 古典文献智能研究助手

基于 Python + Streamlit 构建的古籍智能分析平台，内置《论语》《大学》《中庸》，支持任意古籍文本上传。

## 功能

- 📊 **词频分析**：自动统计高频字并生成可视化图表，支持导出 CSV/Excel
- 🔍 **概念对比**：输入两个概念，精准检索共现章句并高亮显示
- 💬 **多轮问答**：基于原文内容的 AI 问答，引用具体章句作答
- 🔄 **繁简自动转换**：自动处理繁体古籍文本

## 技术栈

Python · Streamlit · DeepSeek API · OpenCC · Pandas · Matplotlib

## 数据验证

《论语》中「仁」出现 110 次，「仁」「礼」共现 4 条，集中体现「克己复礼为仁」等核心义理。

## 使用方法

1. 安装依赖：`pip install streamlit openai pandas matplotlib opencc-python-reimplemented openpyxl`
2. 运行：`streamlit run app.py`
