# langtool
Mobilní aplikace pro studium jazyků.

## Struktura
V tomto repozitáři se nachází primárně serverová část projektu napsaná v Pythonu+Djangu. Klientská část se nachází v gitovém submodulu [langtool_mobile](https://github.com/lesves/langtool_mobile/) a její dokumentaci naleznete tam. Ve zbytku tohoto souboru se budeme zabývat návrhem aplikace a její serverovou částí.

## Návrh
Po několika prototypech jsem došel k tomu, že člověk se primárně učí slova (ne věty), přičemž je důležité mít k nim kontext. Proto si aplikace u každého slova ukládá úroveň jeho znalosti daným uživatelem, přičemž pak uživateli cíleně nabízí ta slova, která mu nejdou. Znalost slova je zkoušena tak, že uživatel dostane větu, ve které je zakryté zkoušené slovo. K dané větě ještě uživatel dostane buďto překlad, anebo nahrávku.

### Databáze
V databázovém návrhu figurují následující entity:
#### Language
 - jazyk, který aplikace podporuje
 - zatím je jejich seznam uveden v settings.py, ovšem jdou měnit i za běhu, do budoucna možná dojde k přepracování

#### Course
 - dvojice jazyků, kterou aplikace podporuje (známý jazyk a učený jazyk).
 - do budoucna není vyloučené přepracování podporující učení se jednoho jazyka s pomocí více než jednoho známého jazyka.

#### Word
 - reprezentuje jedno lemmatizované slovo, tedy základní jednotku učení
 - důležitým údajem je i četnost výskytu daného slova

#### UserWordProgress
 - reprezentuje znalost určitého slova daným uživatelem

#### Sentence
 - zaznamenává větu, lze vyhledávat podle obsažených slov

### Komunikace mezi serverovou a klientskou částí
Probíhá pomocí GraphQL dotazů, kterými zjednodušujeme potenciální úpravy aplikace. Např. kdybychom v budoucnu (což je dost možná v plánu) chtěli přidat filtrování podle např. skupiny slov, anebo jejich četnosti, můžeme tak učinit pouhou změnou odesílaného dotazu v klientské aplikaci. Další výhodou GraphQl je, že prování často menší počet dotazů než jiné řešení, což se u mobilní aplikace hodí.

GraphQL API jsem implementoval pomocí `strawberry-graphql-django`. Tato knihovna je dosti nová a po této zkušenosti se mi zdá, že některé věci v ní ještě nejsou úplně doladěné.

## Instalace a spuštění serverové části
Nejprve je nutné vyjmenovat jazyky v `settings.py` a poté připravit data k nim do složky `data/`. Jedná se primárně o soubory `l1-l2.tsv` a `commonvoice/l2/clips.tsv`. První zmíněný lze získat downloadem dat z databáze vět Tatoeba a druhý lze vygenerovat skriptem `commonvoice_extract.py` ze stažených nahrávet datasetu Common Voice.

Pak je třeba postupně přidat následujícím způsobem všechny podporované jazykové páry a můžeme spustit server:
```
python3 manage.py migrate
python3 manage.py addpair cs en
python3 manage.py addpair cs ru
# Přidáme libovolný počet jazykových párů...
python3 manage.py runserver
```
přičemž k api je přístup na cestě `/graphql`.
