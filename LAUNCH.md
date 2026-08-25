# LoopBreaker — 100+ indirme için yapılacaklar

Bu liste senin yapman gereken adımlar. Kod tarafı hazır.

---

## 1. GitHub’a yükle (15 dk)

```powershell
cd c:\Users\LENOVO\.gemini\antigravity\scratch\loop_breaker
git init
git add .
git commit -m "LoopBreaker: Cursor doom-loop guard with rollback"
```

GitHub’da yeni repo aç: `loop-breaker`  
Sonra:

```powershell
git remote add origin https://github.com/KULLANICI_ADIN/loop-breaker.git
git branch -M main
git push -u origin main
```

`README.md` ve `pyproject.toml` içindeki `your-username` kısımlarını kendi kullanıcı adınla değiştir.

---

## 2. Cursor’a bağla (2 dk)

Aynı klasörde:

```powershell
pip install -e .
loop-breaker install
```

Cursor’u kapat-aç. Agent modunda bir proje aç — hook’lar otomatik çalışır.

Başka projelerde de:

```powershell
cd C:\projem
loop-breaker install
```

---

## 3. PyPI’ye koy (isteğe bağlı, indirmeyi artırır)

```powershell
pip install build twine
python -m build
twine upload dist/*
```

Sonra insanlar şunu yazar:

```powershell
pip install loop-breaker
loop-breaker install
```

---

## 4. Paylaş (en önemli kısım)

Kod tek başına 100 indirme getirmez. Şunları yap:

| Nerede | Ne yaz |
|--------|--------|
| **Reddit** r/cursor, r/LocalLLaMA | “I built a doom-loop guard for Cursor that rolls back broken agent edits” + GitHub link |
| **X / Twitter** | 30 sn ekran kaydı: agent döngüye giriyor → LoopBreaker durduruyor |
| **Hacker News** | Show HN: LoopBreaker – stop Cursor agents from infinite fix loops |
| **Discord** | Cursor community, AI coding sunucuları |

**GIF / video şart.** İnsanlar readme okumaz, 10 saniyelik demo izler.

---

## 5. README’yi doldur

- GitHub repo linkini koy
- Demo GIF ekle (`docs/demo.gif`)
- “Works with Cursor Agent hooks” badge

---

## Gerçekçi beklenti

| Ne yaparsın | Ne olur |
|-------------|---------|
| Sadece GitHub’a at | 0–10 star |
| GitHub + 1 paylaşım | 10–50 |
| GitHub + PyPI + demo video + 3 paylaşım | 100 mümkün |
| Yukarıdakiler + biri gerçekten kullanıp issue açarsa | Gerçek ürün sinyali |

---

## Hızlı test (Cursor’da gerçekten çalışıyor mu?)

1. Küçük bir proje aç
2. `loop-breaker install`
3. Cursor Agent’a bilerek kırık bir şey yaptır (aynı hatayı tekrar ettir)
4. Terminalde veya agent mesajında `LOOP BREAKER INTERVENTION` görürsen → çalışıyor
