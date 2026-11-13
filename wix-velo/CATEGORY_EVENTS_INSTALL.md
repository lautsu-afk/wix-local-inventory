# Velo-tapahtumapohjainen kategoriatietojen synkronointi

## Valmisteltu Wix-sivuston asennettavaksi

Tämä paketti täydentää GitHubin automaattista Wix Catalog V1 → CMS
**Kategoriahierarkia** -synkronointia. Automaattinen GitHub-varmistus suoritetaan
nyt **5 minuutin välein**. Jotta uusi kategoria ilmestyisi CMS:ään heti
luontitapahtuman jälkeen, lisää alla olevat backend-tapahtumakäsittelijät
Wixin nykyiseen julkaistavaan Velo-koodiin.

**HUOM:** pelkkä tämän GitHub-tiedoston luominen ei asenna Velo-tapahtumia
Wixiin. Älä korvaa nykyistä `backend/events.js`-tiedostoa. Siinä on jo
tuotetietojen, varastotietojen, ribbonien, rahtiprofiilien ja puutavaran
päivitystoimintoja.

### 1. Lisää uusi backend-tiedosto

Wix Editor → Kehitystila / Velo → Backend & Public → Backend:
luo tiedosto `categoryHierarchyEvents.js`. Kopioi siihen tämän
hakemiston `categoryHierarchyEvents.js`-tiedoston koko sisältö.

### 2. Muokkaa nykyistä backend/events.js-tiedostoa

Lisää muiden importtien joukkoon:

```javascript
import {
  onCategoryCreated,
  onCategoryUpdated,
  onCategoryDeleted
} from 'backend/categoryHierarchyEvents';
```

Lisää nykyisen `backend/events.js`-tiedoston loppuun kaksi uutta
käsittelijää (jos niitä ei siellä ennestään ole):

```javascript
export async function wixStores_onCollectionCreated(event) {
  await onCategoryCreated(event);
}

export async function wixStores_onCollectionDeleted(event) {
  await onCategoryDeleted(event);
}
```

**TÄRKEÄÄ:** nykyisessä `events.js`-tiedostossa on jo
`wixStores_onCollectionUpdated(event)` -käsittelijä puutavara-automaatiota
varten. **Älä lisää toista samannimistä funktiota.** Jos haluat myös
nimimuutosten tapahtumapohjaisen synkronoinnin, lisää *olemassa olevan*
käsittelijän sisälle:

```javascript
await onCategoryUpdated(event);
```

Jos käsittelijä ei ole vielä `async`, vaihda sen määritelmä
`export async function wixStores_onCollectionUpdated(event)` -muotoon.
Säilytä sen nykyinen puutavaran käsittely täysin ennallaan.

### 3. Julkaise ja testaa

Julkaise Wix-sivusto. Wix-taustatapahtumat eivät toimi editorin
esikatselussa.

Luo Wix Storesiin testikategoria oikealla käyttöliittymällä ja
tarkista, että `Kategoriahierarkia`-kokoelmaan ilmestyy vastaava
rivi: oikea `Kategoria` ja sama Wix UUID. Uusi rivi saa `Pääkategoria=false`,
ja `Yläkategoria` on tyhjä, jotta voit valita sen itse.
Wix Catalog V1:n tapahtuma ei takaa URL-slugin saatavuutta, joten
`Kategorian URL-tunniste` voi täyttyä seuraavassa 5 minuutin tarkistuksessa.

### Mikä muuttuu ja mikä ei?

- Uusi kategoria: CMS-rivi lisätään heti tapahtuman saavuttua.
- Kategorian poisto: CMS-rivi poistetaan saman tapahtuman perusteella.
- Kategorian nimen muutos: päivitetään tapahtumassa, jos lisäsit
  `onCategoryUpdated`-kutsun olemassa olevaan käsittelijään; muutoin
  enintään 5 minuutin välein.
- Yläkategoriaa `parent` ja `Pääkategoria`-asetusta ei ylikirjoiteta.
- Tuotteita, niiden Store-kategorioita, varastosaldoja, ostotietoja,
  toimitusprofiileja tai muita `events.js`-käsittelijöitä ei muuteta.
- GitHubin 5 minuutin varmistus toimii, vaikka tapahtuma jäisi käsittelemättä.

Velo-tapahtumien viitteet:
https://dev.wix.com/docs/velo/apis/wix-stores-backend/events/on-collection-created
https://dev.wix.com/docs/velo/apis/wix-stores-backend/events/on-collection-updated
https://dev.wix.com/docs/velo/apis/wix-stores-backend/events/on-collection-deleted
