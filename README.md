# Kleding-aanbod

Zelfstandige gratis kledingzoeker. Dit project gebruikt geen Apify- of Scrappa-tegoed en heeft geen koppeling met de Mercedes-repository.

## Instellen

Het profiel staat ingesteld voor een gespierde man van 38 jaar, 183 cm en 100 kg. De agent zoekt sportshirts en korte sportbroeken in het voorlopige venster XL–2XL. Dat is bewust geen maatgarantie: noteer later borst-, taille- en heupomvang in `search-profiles.json` om miskopen door merkverschillen beter te voorkomen.

Een product wordt alleen toegelaten als de beschikbare informatie zowel een veilige donkere/gemêleerde/bedrukte kleur als sneldrogende of vochtafvoerende techniek ondersteunt. Katoenrijke en lichte effen kleding wordt geweerd. Aanbiedingen krijgen voorrang bij vergelijkbare geschiktheid, maar zijn niet verplicht.

Maak een nieuwe GitHub-repository en voeg uitsluitend deze secrets toe:

- `CLOTHING_OPENROUTER_API_KEY` (optioneel; zonder sleutel werkt de lokale score)
- `CLOTHING_RESEND_API_KEY`
- `CLOTHING_MAIL_TO`

Gebruik bij voorkeur aparte provideraccounts of aparte kledingkeys. De workflow gebruikt eigen secretnamen en kan daardoor nooit per ongeluk Mercedes-secrets aanspreken.

De workflow controleert tweemaal per dag, maar zoekt maximaal eens per 72 uur en maximaal 10 keer per kalendermaand. Na de eerste mail wordt alleen opnieuw gemaild bij een nieuw passend product of een lagere prijs.

Volledige onzichtbaarheid van zweet kan niet op afstand worden gegarandeerd. De selectie minimaliseert het risico en moet onzekerheid expliciet tonen. Zonder voldoende onderbouwing wordt geen product gemaild.

De automatische collector combineert browseronderzoek met `verified-products.json`. In dat bestand staan alleen handmatig tegen officiële productpagina's gecontroleerde kandidaten. Daarmee blijft er een betrouwbare basis wanneer een winkel geautomatiseerde paginatoegang tijdelijk blokkeert.

## Lokaal testen

```powershell
python -m pip install -r requirements.txt
python find-clothing.py
python select-clothing.py
python make-report.py
```
