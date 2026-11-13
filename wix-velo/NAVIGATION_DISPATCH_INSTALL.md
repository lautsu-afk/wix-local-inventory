# CMS-muutoksesta GitHub-navigaatiopäivitys (asennus)

## Tila 13.11.2026

GitHubissa `.github/workflows/update-navigation.yml` vastaanottaa nyt
`repository_dispatch`-tapahtuman tyypillä `wix-category-navigation`.
Se ajaa vain `generate_navigation.py`-skriptin. Inventaarion työnkulkua
ei tarvitse muuttaa. **Tämä ei yksinään todista tapahtumaketjua toimivaksi.**

Velo-aputiedosto `wix-velo/navigationDispatch.js` on GitHubissa, mutta
se ei ole vielä käytössä julkaistulla Wix-sivustolla. Asennus vaatii
Wix Editorin backend-koodin muutoksen ja GitHubin käyttöoikeustunnuksen.

## 1. Tee rajattu GitHub-tunnus

GitHub → Settings → Developer settings → Personal access tokens →
Fine-grained tokens:

- Resource owner: `lautsu-afk`
- Repository access: **Only select repositories** → `wix-local-inventory`
- Repository permissions: **Contents: Read and write**
- Valitse mahdollisimman lyhyt, ylläpidettävissä oleva voimassaoloaika.
- Älä liitä tunnusta lähdekoodiin, chattiin tai GitHub-tiedostoihin.

Wix-sivuston dashboardissa luo Secrets Manageriin salaisuus nimellä
`GITHUB_NAVIGATION_TOKEN` ja arvoksi juuri luotu token.

GitHub `repository_dispatch` vaatii fine-grained-tokenilta Contents: write.
GitHub antaa onnistuneesta pyynnöstä HTTP 204.

## 2. Lisää yksi uusi Wix-backend-moduuli

Kopioi GitHubin tiedosto
`wix-velo/navigationDispatch.js`
Wixin backend-tiedostoksi
`backend/navigationDispatch.js`.

Älä luo julkista web-moduulia. Tunnus haetaan vain taustakoodissa
`wix-secrets-backend.v2`-rajapinnasta.

## 3. Lisää CMS-koukut nykyiseen backend/data.js-tiedostoon

Älä korvaa nykyistä tiedostoa: siellä on jo
ProductShippingProfiles-, puutavara- ja muita synkronointikoukkuja.

Lisää import olemassa olevien importien joukkoon:

```javascript
import { requestNavigationRefresh } from "backend/navigationDispatch";
```

Lisää kolme käsittelijää (vain jos vastaavia ei vielä ole):

```javascript
export async function Kategoriahierarkia_afterInsert(item, context) {
  await requestNavigationRefresh("cms-insert");
  return item;
}

export async function Kategoriahierarkia_afterUpdate(item, context) {
  await requestNavigationRefresh("cms-update");
  return item;
}

export async function Kategoriahierarkia_afterRemove(item, context) {
  await requestNavigationRefresh("cms-remove");
  return item;
}
```

Jos jokin näistä koukuista on jo käytössä, lisää vain
`await requestNavigationRefresh(...)` siihen olemassa olevaan funktioon:
samaan kokoelmaan ei saa tehdä toista samannimistä exporttia.
Koukut eivät kirjoita varasto-, tuote- tai lähetyskenttiä.
Ne säilyttävät `return item`-palautteen.

GitHubin CMS-synkronointiajo voi myös kirjoittaa CMS:ään muuttuneita
nimiä/slug-tietoja: se saattaa aiheuttaa yhden ylimääräisen dispatchin.
Työnkulun yhteinen `concurrency`-ryhmä sarjoittaa navigaatiotyöt,
ja ne lukevat aina tuoreet CMS-tiedot. Jatkuvan päivityssilmukan varalta
tarkista ensitestissä, ettei samoja ajoja synny loputtomasti.

## 4. Julkaise ja testaa todellisella CMS-muutoksella

1. Julkaise Wix-sivusto (pelkkä editorin esikatselu ei riitä).
2. Vaihda olemassa olevan kategorian yläkategoria CMS:n
   `Kategoriahierarkia`-kokoelmassa, tallenna ja vaihda tarvittaessa takaisin.
3. Tarkista Wix Logsista `Kategoriahierarkia: GitHub navigation refresh
   requested` tai virhe.
4. GitHub → Actions → `Update Wix category navigation`:
   uuden ajon **Event = repository_dispatch** pitää näkyä ja
   `navigation`-jobin pitää päättyä **success**-tilaan.
5. Tarkista päivitetty `docs/navigation.json`, GitHub Pagesin julkaisu
   sekä live-tuotteen breadcrumb. Pelkkä HTTP 204 ei todista onnistumista.

Jos GitHubiin ei ilmesty ajokertaa, älä väitä ajastusta toimivaksi.
Tarkista Wix Logs, tokenin oikeudet, workflow-tilan enabled-arvo ja
`repository_dispatch`-tapahtuman nimi.

## Lisäksi: Wix Stores -kategorioiden syntyminen

Wix Stores Catalog V1 -luonti- ja poistotapahtumien valmistellut
käsittelijät ovat tiedostoissa
`wix-velo/categoryHierarchyEvents.js` sekä
`wix-velo/CATEGORY_EVENTS_INSTALL.md`.
Ne pitää asentaa erikseen, jotta uuden/poistetun Wix Stores -kategorian
CMS-rivi päivittyy välittömästi ja edellä oleva CMS-koukku laukeaa.

## Varajärjestely

Jätä toistaiseksi nykyiset 5 minuutin cron-asetukset voimaan, kunnes
Wix-tapahtumaketju on testattu. `update-inventory.yml`-tiedostoa ja
sen yöajon työnkulun ehtoja ei saa muuttaa tässä asennuksessa.
