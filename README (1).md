# 📡 Trend Pulse v2 — Google Trends Dashboard

Trend Pulse is a powerful **Streamlit-based dashboard** that lets you compare multiple keywords using **Google Trends data** in real-time.

It provides deep insights like:
- 📈 Interest over time
- 🌍 Geographic distribution
- 🔍 Related queries
- 📊 Advanced analytics
- 🔥 Trending searches

---

## 🚀 Features

- Compare up to **5 keywords simultaneously**
- Interactive **Plotly visualizations**
- Real-time data using **pytrends**
- Advanced analytics:
  - Correlation matrix
  - Rolling averages
  - Momentum tracking
  - Distribution (Box plots)
- Geographic heatmaps
- Trending search explorer
- CSV download support

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Data Source:** Google Trends (via pytrends)
- **Visualization:** Plotly
- **Backend:** Python (Pandas)

---

## 📂 Project Structure

```
.
├── trends_app.py        # Main Streamlit application
├── requirements.txt    # Dependencies
└── README.md           # Project documentation
```

---

## ⚙️ Installation

### 1. Clone the repository
```
git clone <your-repo-url>
cd trend-pulse
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

Dependencies used:  
- streamlit  
- pytrends  
- plotly  
- pandas  

(See: requirements.txt)

---

## ▶️ Run the App

```
streamlit run trends_app.py
```

---

## 🧠 How It Works

1. Enter keywords (max 5)
2. Select:
   - Time period
   - Region
   - Category
3. Click **Analyze Trends**
4. Explore multiple dashboards:
   - 📈 Time Series
   - 🌍 Maps
   - 🔍 Queries
   - 📊 Deep Analytics
   - 🔥 Trending

---

## ⚡ Special Fix (Important)

This project includes a **compatibility patch for urllib3 v2**:

- Fixes `method_whitelist` deprecation issue in pytrends
- Ensures smooth execution without crashes

---

## 📊 Data Notes

- Data is **normalized (0–100)**
- 100 = peak popularity
- Cached for **5 minutes** per query

---

## 📦 Example Keywords

Try:
- ChatGPT
- Gemini
- Claude AI
- Copilot

---

## 🧩 Future Improvements

- Export to PDF reports
- AI-based trend prediction
- Keyword suggestions
- Mobile optimization

---

## 👨‍💻 Author

Developed by **Unmilan Das**

---

## ⭐ Support

If you like this project:
- ⭐ Star the repo
- 🍴 Fork it
- 🚀 Share with others

---

## 📜 License

This project is for educational purposes.
