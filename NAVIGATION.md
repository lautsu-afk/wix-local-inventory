# Lautamaki.fi – automaattiset kategoriat ja murupolut

## Käytössä

Wix Stores Catalog V1:n tuotetiedot ja kategoriat haetaan automaattisesti GitHub Actionsilla **30 minuutin välein** (ja erikseen, kun tämän toteutuksen asetuksia päivitetään). Päivitys luo:

- `docs/navigation.json` – kategoriapolut, alakategoriavalikot ja tuotteiden ensisijainen kategoriavalinta.
- `docs/navigation.js` – sama tieto sivuston käyttämässä muodossa.

Julkaisu tapahtuu automaattisesti GitHub Pagesin kautta. Wix-sivuston erillinen Custom Embed -datalataaja lukee julkisen `navigation.js`-tiedoston. Tiedosto haetaan sivun latauksen yhteydessä; URL päivittyy 15 minuutin välein. Myös kolmen olemassa olevan navigaatiokoodin staattinen versio säilytettiin, jos etätietoa ei ole saatavilla.

## Päivittyy automaattisesti

- Wix-kategorian nimi tai URL-slug muuttuu: kategoriapolut ja alakategorialinkit käyttävät ajantasaisia tietoja.
- Tuote lisätään, poistetaan tai sen kategoriat muuttuvat: tuotesivun polku päivittyy tuotteen jäsenyyden perusteella.
- Kategoria poistetaan tai piilotetaan: sitä ei enää lisätä julkaistuun navigaatioon.
- Uusi kategoria: jos sillä on yksiselitteinen pääkategoria tuoteyhteyksien perusteella, se tulee kyseisen pääkategorian alle. Muuten se jää suoraan **Kaikki tuotteet** -tason alle, kunnes yläkategoria määritellään.

Aiemmin luodut kategorialinkit, fontit, värit ja murupolkujen muotoilu on säilytetty. Tarkoitus ei ole muuttaa tuoteluetteloa tai varastosaldoja.

## Tärkeä V1-rajoitus: yläkategoria ei ole Wixin oma ominaisuus

Catalog V1:n kategoriat ovat rinnakkaisia kokoelmia, eivät oikeita sisäkkäisiä kategorioita. Siksi jo määritellyn alakategorian **yläkategorian siirtoa** ei voida luotettavasti lukea Wixistä automaattisesti.

- Yläkategoriat on määritelty pysyvillä Wix-kategorian ID-tunnisteilla tiedostossa `navigation_config.json` kohdassa `parent_by_category_id`.
- Kun haluat muuttaa vain kategorian nimeä, tuotteita tai näkyvyyttä, muutokset päivittyvät Wixistä automaattisesti.
- Kun haluat siirtää koko alakategorian toisen pääkategorian alle, muuta `navigation_config.json`-määritystä (tai pyydä ChatGPT:tä tekemään muutos). Pelkkä tuotteen lisääminen toiseen pääkategoriaan ei ole yksiselitteinen hierarkiamuutos, sillä sama tuote voi olla useissa ryhmissä.
- `main_display_name_overrides` säilyttää erikseen sovitut näkyvät nimet, esim. **Rakennustarvikkeet- ja tuotteet** otsikossa ja **Rakennustarvikkeet** murupolussa sekä **Sähkötarvikkeet**-linkin oikeinkirjoituksen.

## Toimintatavan tarkistus

`Actions → Update Wix category navigation` näyttää synkronointiajon tilan. Päivitystä voi tarvittaessa käynnistää myös **Run workflow** -painikkeella. Selaimen näkyvä päivitys voi tulla GitHub Pagesin julkaisun ja välimuistin vuoksi vasta jonkin aikaa onnistuneen ajon jälkeen.

## Tiedostot

- `navigation_config.json` – pysyvä hierarkia
- `generate_navigation.py` – Wix Catalog V1 -datan haku, ensisijaisen kategorian valinta, tiedoston muodostus
- `.github/workflows/update-navigation.yml` – ajastus ja julkaisu
- `docs/navigation.json`, `docs/navigation.js` – sivuston lukemat tuotetut tiedot

Tämä toteutus on riippumaton olemassa olevasta `update_inventory.py`-syötteestä ja sen työnkulusta.
