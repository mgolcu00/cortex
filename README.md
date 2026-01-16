# Confluence Q&A

Confluence dokumanlarinizi kullanarak sorulari cevaplayan AI destekli bilgi asistani.

## Ozellikler

- **Semantik Arama**: OpenAI embeddings ve pgvector ile vektor tabanli arama
- **AI Destekli Cevaplar**: GPT-4/GPT-5 tabanli akilli yanitlar ve kaynak gosterimi
- **Gercek Zamanli Senkronizasyon**: Confluence Cloud ile otomatik senkronizasyon
- **Modern UI**: React tabanli sohbet arayuzu (dark tema)
- **Session Yonetimi**: PostgreSQL destekli kalici sohbet gecmisi
- **Kullanim Analitikleri**: Token kullanimi, maliyet takibi ve API istatistikleri

## Hizli Baslangic

### 1. Gereksinimleri Kurun

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (pgvector extension ile)

### 2. Projeyi Indirin

```bash
git clone <repository-url>
cd confluence-qa
```

### 3. Ortam Degiskenlerini Ayarlayin

`.env.example` dosyasini `.env` olarak kopyalayip duzenleyin:

```bash
cp .env.example .env
```

`.env` dosyasini acin ve su degerleri ayarlayin:

```env
# OpenAI (Zorunlu)
OPENAI_API_KEY=sk-your-api-key-here

# PostgreSQL (Zorunlu)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/confluence_qa

# Confluence (Zorunlu)
CONFLUENCE_BASE_URL=https://your-site.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@company.com
CONFLUENCE_API_TOKEN=your-api-token
```

### 4. Uygulamayi Baslatin

```bash
./run.sh
```

Bu komut:
1. Python sanal ortamini olusturur
2. Python bagimliklarini yukler
3. Frontend'i derler (ilk calistirmada)
4. Uygulamayi baslatir

Tarayicinizda http://localhost:8000 adresini acin.

### 5. Confluence'i Senkronize Edin

1. Ayarlar sayfasina gidin
2. "Sync Baslat" butonuna tiklayin
3. Senkronizasyonun tamamlanmasini bekleyin

---

## Docker ile Kurulum

Docker, tum bagimliliklari tek komutla ayaga kaldirir. PostgreSQL, pgvector ve uygulama otomatik olarak kurulur.

### Adim 1: .env Dosyasini Hazirlayin

```bash
cp .env.example .env
```

`.env` dosyasinda su degerleri doldurun:

```env
# OpenAI API Key (zorunlu)
OPENAI_API_KEY=sk-your-openai-api-key

# Confluence Bilgileri (zorunlu)
CONFLUENCE_BASE_URL=https://your-site.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@company.com
CONFLUENCE_API_TOKEN=your-confluence-api-token

# PostgreSQL (Docker icin varsayilan)
POSTGRES_USER=confluence
POSTGRES_PASSWORD=confluence
POSTGRES_DB=confluence_qa

# Diger ayarlar varsayilan degerlerle calisir
```

> **Not**: Docker Compose `.env` dosyasini otomatik okur. Environment degiskenlerini ayri ayri girmenize gerek yok.

### Adim 2: Servisleri Baslatin

```bash
docker-compose up -d
```

Bu komut:
1. PostgreSQL + pgvector veritabanini baslatir
2. Frontend'i derler (Node.js)
3. Backend'i baslatir (Python/FastAPI)
4. Tum servisleri birbirine baglar

### Adim 3: Loglari Kontrol Edin

```bash
# Tum loglar
docker-compose logs -f

# Sadece uygulama loglari
docker-compose logs -f app

# Sadece veritabani loglari
docker-compose logs -f db
```

### Adim 4: Uygulamaya Erisin

Tarayicinizda http://localhost:8000 adresini acin.

### Servisleri Durdurun

```bash
# Durdur (verileri koru)
docker-compose down

# Durdur ve tum verileri sil
docker-compose down -v
```

### Docker Sorun Giderme

**Build hatasi:**
```bash
# Cache'i temizleyip yeniden derle
docker-compose build --no-cache
docker-compose up -d
```

**Port kullaniliyor:**
```bash
# 5432 veya 8000 portu baskasi tarafindan kullaniliyorsa
# docker-compose.yml'de portlari degistirin:
# - "5433:5432"  # PostgreSQL
# - "8001:8000"  # Uygulama
```

**Veritabani baglanti hatasi:**
```bash
# Veritabaninin hazir olmasini bekleyin
docker-compose logs db
# "database system is ready to accept connections" mesajini gorun
```

---

## Gelistirme Ortami

### Backend

```bash
# Sanal ortam olustur
python -m venv .venv
source .venv/bin/activate

# Bagimliliklari yukle
pip install -r requirements.txt

# Sunucuyu baslat (hot reload)
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend

# Bagimliliklari yukle
npm install

# Gelistirme sunucusu (HMR)
npm run dev

# Production build
npm run build
```

---

## Proje Yapisi

```
confluence-qa/
├── app/                      # Backend (FastAPI)
│   ├── main.py              # API endpoints
│   ├── config.py            # Ortam degiskenleri
│   ├── agent.py             # OpenAI Agent + Session yonetimi
│   ├── db/
│   │   ├── database.py      # PostgreSQL baglantisi
│   │   ├── models.py        # SQLAlchemy modelleri
│   │   └── vector_store.py  # pgvector islemleri
│   ├── confluence/
│   │   └── client.py        # Confluence API istemcisi
│   └── ingest/
│       ├── sync.py          # Senkronizasyon
│       ├── chunker.py       # Metin parcalama
│       └── embedder.py      # OpenAI embeddings
│
├── frontend/                 # Frontend (React + Vite)
│   ├── src/
│   │   ├── pages/           # Sayfa bilesenleri
│   │   ├── components/      # UI bilesenleri
│   │   └── lib/             # API, store, utils
│   └── package.json
│
├── docker-compose.yml        # Docker servisleri
├── Dockerfile               # Uygulama image'i
├── run.sh                   # Gelistirme baslat scripti
├── requirements.txt         # Python bagimliliklari
├── .env.example             # Ornek ortam degiskenleri
└── README.md
```

---

## API Dokumantasyonu

### Chat

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| POST | `/chat` | Mesaj gonder, AI yaniti al |

### Sessions

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| GET | `/sessions` | Tum oturumlari listele |
| GET | `/sessions/{id}` | Oturum detayi |
| DELETE | `/sessions/{id}` | Oturumu sil |

### Veritabani

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| GET | `/api/db/pages` | Indekslenmis sayfalari listele |
| GET | `/api/db/pages/{id}` | Sayfa detayi |
| GET | `/api/db/spaces` | Confluence space'lerini listele |

### Senkronizasyon

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| POST | `/sync/run` | Senkronizasyon baslat |
| GET | `/sync/status` | Senkronizasyon durumu |

### Ayarlar

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| GET | `/api/config` | Mevcut konfigurasyon |
| GET | `/api/instructions` | Agent talimatlari |
| PUT | `/api/instructions` | Talimatlari guncelle |
| GET | `/api/stats` | Kullanim istatistikleri |

---

## Konfigurasyon

### Ortam Degiskenleri

| Degisken | Zorunlu | Varsayilan | Aciklama |
|----------|---------|------------|----------|
| `OPENAI_API_KEY` | Evet | - | OpenAI API anahtari |
| `DATABASE_URL` | Evet | - | PostgreSQL baglanti URL'i |
| `CONFLUENCE_BASE_URL` | Evet | - | Confluence URL (https://xxx.atlassian.net/wiki) |
| `CONFLUENCE_EMAIL` | Evet | - | Confluence email |
| `CONFLUENCE_API_TOKEN` | Evet | - | Confluence API token |
| `CHAT_MODEL` | Hayir | gpt-4o | Chat modeli |
| `EMBEDDING_MODEL` | Hayir | text-embedding-3-small | Embedding modeli |
| `SYNC_INTERVAL_MINUTES` | Hayir | 60 | Otomatik sync araligi |
| `LOG_LEVEL` | Hayir | INFO | Log seviyesi |

### Agent Talimatlari

Ayarlar sayfasindan agent'in davranisini ozellestirin:
- Ne zaman arama yapacagi
- Cevap formati ve tonu
- Kaynak gosterim sekli

---

## Sorun Giderme

### pgvector Extension Bulunamadi

```bash
# macOS
brew install pgvector
psql confluence_qa -c "CREATE EXTENSION vector;"

# Ubuntu/Debian
sudo apt install postgresql-15-pgvector
psql confluence_qa -c "CREATE EXTENSION vector;"
```

### Confluence API 401 Hatasi

1. API token'inizi kontrol edin: https://id.atlassian.com/manage/api-tokens
2. Email'in Atlassian hesabinizla eslestigi dogrulayin
3. BASE_URL'nin `/wiki` ile bittiginden emin olun

### Bos Arama Sonuclari

1. Once tam senkronizasyon yapin
2. Sayfalarin metin icerigi oldugundan emin olun
3. Ayarlar'dan senkronizasyon durumunu kontrol edin

---

## Lisans

MIT License
# cortex
