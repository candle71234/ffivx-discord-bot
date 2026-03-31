# 🌱 FF14 Discord 公會工具機器人

---

> 💡 把 FF14 的「時間管理」全部自動化  
> 不用記、不會忘、直接提醒

---

## ✨ 功能總覽

### 🚢 潛水艇提醒
- ⏰ 自訂時間提醒（支援 `1d3h12min`）
- 🔔 自動 @ 身分組
- 📋 查看 / 取消提醒
- 💾 JSON 持久化

### 📅 每週 / 每日提醒
- 🪙 仙人彩（每週六）
- 📖 天書奇談 / 老主顧（每週二）

### 🧑‍🌾 公會農田系統
- 🌱 種植（單格 / 多格 / 全部）
- 💧 澆水（防止枯萎）
- 🧪 施肥（加速成熟）
- 🌾 收成（成熟 / 強制收）
- 🪓 拔除（確認機制）

#### ⏰ 自動提醒
- 成熟提醒（會 ping）
- 24 小時枯萎提醒
- 緊急枯萎提醒（會 ping）

---

## 🎮 指令快速表

### 🚢 潛水艇
| 指令 | 功能 |
|------|------|
| /sub add | 新增提醒 |
| /sub list | 查看提醒 |
| /sub cancel | 取消提醒 |

### 🧑‍🌾 農田
| 指令 | 功能 |
|------|------|
| /farm | 查看農田 |
| /farmslot | 查看單格 |
| /plant | 種植 |
| /water | 澆水 |
| /fertilize | 施肥 |
| /harvest | 收成 |
| /uproot | 拔除 |
| /crops | 作物列表 |

---

## 📌 格子輸入格式

```
1           # 單格
1246        # 多格
1,2,4,6     # 多格
all         # 全部
```

---

## ⚙️ 環境設定

### 安裝
```
pip install discord.py python-dotenv
```

### 環境變數
```
DISCORD_BOT_TOKEN=你的Token
REMINDER_CHANNEL_ID=頻道ID
DAILY_ROUTINE_ROLE_ID=每日身分組
WEEKLY_ROUTINE_ROLE_ID=每週身分組
```

### 啟動
```
python bot.py
```

---

## 🧠 系統架構

```
project/
├── bot.py
├── config.py
├── farm_system.py
├── farm_seeds.py
└── data/
    ├── submarine_jobs.json
    └── farm_data.json
```

---

## 💡 設計理念

把 FF14 日常提醒，讓玩家的遊玩體驗更加美好！
