# Lautamaki.fi – kategoriat ja murupolut

## Hierarkian hallinta Wix CMS:ssä

**Kategoriahierarkia** on sivuston Wix CMS:ään perustettu kokoelma. Sieltä voi muuttaa alaryhmän yläkategorian ilman koodia ja GitHubin muokkaamista.

1. Avaa M. Lautamäki Oy -sivuston Wix-hallintapaneelista **CMS** ja kokoelma **Kategoriahierarkia**.
2. Etsi muokattava rivi **Kategoria**-sarakkeesta.
3. Avaa **Yläkategoria (valitse listasta)** -kenttä. Valitse haluamasi yläkategoria sen nimellä tai tyhjennä kenttä, jos haluat kategorian suoraan **Kaikki tuotteet** -tason alle.
4. Tallenna muutos. GitHub Actions lukee muutoksen automaattisesti 5 minuutin välein. GitHub Pagesin julkaisu ja selaimen 15 minuutin välimuisti voivat pidentää näkyvyyden viivettä.

**Pääkategoria**-valintaruutu tarkoittaa ylimmän tason pääryhmää. Pääkategorian yläkategoria jätetään tyhjäksi.

**Kategoria**, **Wix-kategorian tunniste (älä muuta)** ja **Kategorian URL-tunniste** ovat Wix Storesista synkronoitavia tietoja. Älä muokkaa niitä CMS:ssä; nimen/osoitteen muutos tehdään Wix Storesin kategoriasta. Automaatti korjaa niiden CMS-arvot tarvittaessa.

**Älä poista CMS:n kategorian rivejä**. Varsinainen Wix Stores -kategorian poistaminen tai piilottaminen tehdään Wix Storesin hallinnasta. Vältä myös kategoriasta itseensä osoittavia tai kehän muodostavia yläkategorioita.

## Tekniset rajat

Sivusto käyttää Wix Stores **Catalog V1** -mallia, jossa Store-kategoriat ovat rinnakkaisia eikä Wixillä ole erillistä natiivihierarkiaa. CMS:n `parent`-viitteet ohjaavat verkkokaupan erillistä navigaatiota, **eivät muuta tuotteiden Wix Stores -kategorioita tai varastosaldoja**.

Wix-kategorian nimen, URL-osoitteen, näkyvyyden tai tuotteen kategorian muutokset poimitaan suoraan Stores API:sta. Kategoriahierarkia luetaan Wix CMS:stä. Uusi Wix Stores -kategoria lisätään automaattisesti myös CMS-listalle; sille yritetään päätellä yläkategoria yksiselitteisestä tuotteiden pääryhmäjäsenyydestä. Muussa tapauksessa se jää Kaikki tuotteet -tasolle, kunnes yläkategoria valitaan CMS:ssä.

Kaikille kategorioille, joilla on suoria alaryhmiä, syntyy **Alakategoriat**-valikko; alaryhmien ja tuotteiden breadcrumbit rakentuvat saman CMS-hierarkian mukaan.

## Ajastuksen toiminnan tarkistaminen

**Huomio 13.11.2026:** Ajastuksen viiden minuutin cron-asetus oli
GitHubissa, mutta ajohistoriassa näkyi vain `push`-käynnistyksiä,
ei vielä yhtään `schedule`-käynnistystä. GitHubin cron muutettiin
arvosta `*/5 * * * *` arvoon `2-59/5 * * * *`, jotta aikataulu
rekisteröityy uudelleen ja väistää tunnin alun kuormituspiikin.
Tämä ei ole vielä näyttö siitä, että tulevat `schedule`-ajot
käynnistyvät säännöllisesti.

Kunnes `schedule`-ajo on vahvistettu ajohistoriasta, voit päivittää
hierarkiamuutoksen heti GitHubista:
**Actions → Update Wix category navigation → Run workflow**.
Tämä muodostaa uusimman CMS-puun, jonka sivu lataa GitHub Pagesista.

## Päivitys ja varajärjestelmä

GitHub Actions -työnkulku `Update Wix category navigation` suoritetaan **5 minuutin välein** ja kun sen lähdekoodia muutetaan. Ajo hakee:

- Wixin Catalog V1 -tuotteet ja -kategoriat
- Wixin **Kategoriahierarkia** CMS -rivien `parent`-viittaukset sekä `isMain`-valinnat
- GitHub-tiedoston `navigation_config.json` nimen/otsikon poikkeussäännöt ja pääkategorioiden kuvaukset

Ajo luo `docs/navigation.json` ja `docs/navigation.js` ja julkaisee ne GitHub Pagesiin. Wix-sivuston nykyinen datalataus lukee JS-tiedoston sivulle; kolmen nykyisen navigaatiokoodin aiempi data säilyy varalla, jos tiedostoa ei saada ladattua.

Mikäli CMS:n haku epäonnistuu, automaatio keskeyttää julkaisun eikä korvaa asiakkaan hierarkiamuutoksia vanhoilla tiedoilla. Navigaatio pysyy edellisen onnistuneen julkaisutiedoston mukaisena.

## Tiedostot

- `generate_navigation.py`: live-tietojen haku, CMS:n synkronointi ja navigaation muodostus
- `navigation_config.json`: esitystavan poikkeukset sekä alkuperäisen rakenteen varatiedot; **ei enää normaali yläkategorioiden muokkauspaikka**
- `.github/workflows/update-navigation.yml`: 5 minuutin ajastus
- `docs/navigation.json` ja `docs/navigation.js`: julkaistavat navigaatiotiedot

Päivityksen onnistumisen voi tarkistaa GitHubin **Actions → Update Wix category navigation** -näkymästä tai käynnistää siellä käsin **Run workflow**.

Wix Velo -tapahtumapohjaisen välittömän päivityksen erillinen asennusohje: [wix-velo/CATEGORY_EVENTS_INSTALL.md](wix-velo/CATEGORY_EVENTS_INSTALL.md). Tapahtumakäsittelijät on valmisteltu, mutta niitä ei ole vielä lisätty julkaistuun Wix backend/events.js -tiedostoon.

Tämä toteutus on erillinen nykyisestä Google Merchant Centerin varasto-/Shopping-syöteautomaatiosta.
