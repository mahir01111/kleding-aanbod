# Kleding-aanbod

Zelfstandige gratis kledingzoeker. Dit project gebruikt geen Apify- of Scrappa-tegoed en heeft geen koppeling met de Mercedes-repository.

## Instellen

Het profiel staat ingesteld voor een gespierde man van 38 jaar, 183 cm en 100 kg. De agent zoekt sportshirts en korte sportbroeken in het voorlopige venster XL–2XL. Dat is bewust geen maatgarantie: noteer later borst-, taille- en heupomvang in `search-profiles.json` om miskopen door merkverschillen beter te voorkomen.

Een product wordt alleen toegelaten als de beschikbare informatie zowel een veilige donkere/gemêleerde/bedrukte kleur als sneldrogende of vochtafvoerende techniek ondersteunt. Katoenrijke en lichte effen kleding wordt geweerd. Aanbiedingen krijgen voorrang bij vergelijkbare geschiktheid, maar zijn niet verplicht.

Maak een nieuwe GitHub-repository en voeg uitsluitend deze secrets toe:

- `CLOTHING_OPENROUTER_API_KEY` (optioneel; zonder sleutel werkt de lokale score)
- `CLOTHING_DEEPSEEK_API_KEY` (primaire AI; OpenRouter blijft reserve)
- `CLOTHING_RESEND_API_KEY`
- `CLOTHING_MAIL_TO`

Gebruik bij voorkeur aparte provideraccounts of aparte kledingkeys. De workflow gebruikt eigen secretnamen en kan daardoor nooit per ongeluk Mercedes-secrets aanspreken.

De beoordelingsvolgorde is DeepSeek V4 Flash, daarna OpenRouter Free Router en ten slotte de volledig lokale score. Daardoor stopt de dagelijkse mail niet wanneer een AI-provider tijdelijk onbeschikbaar is of het DeepSeek-saldo op is.

De workflow zoekt iedere avond rond 20:55 Nederlandse tijd en mailt rond 21:00 uur de beste maximaal 10 passende producten, ook als dezelfde producten opnieuw winnen. Er zijn maximaal 31 runs per kalendermaand. Aanbiedingen met een door de applicatie gemeten prijsdaling staan bovenaan; daarna bepalen zweetbewijs, AI-beoordeling, maatkans, reviews en retourrisico de volgorde.

De applicatie bewaart maximaal 24 prijswaarnemingen per product. Alleen een daling tegenover een eigen eerdere waarneming heet een bewezen aanbieding. Dubbele producten worden verwijderd. Reviews worden gecontroleerd op positieve en negatieve signalen over zweetplekken en doorschijnen. De mail toont daarnaast een zweetbewijsscore, persoonlijke maatkans, passende live maten en retourrisico. Negatieve relevante reviews, ontbrekende maatvoorraad, ontbrekende foto of onvoldoende bewijs blokkeren een product.

Volledige onzichtbaarheid van zweet kan niet op afstand worden gegarandeerd. De selectie minimaliseert het risico en moet onzekerheid expliciet tonen. Zonder voldoende onderbouwing wordt geen product gemaild.

De automatische collector combineert browseronderzoek met `verified-products.json`. In dat bestand staan alleen handmatig tegen officiële productpagina's gecontroleerde kandidaten. Daarmee blijft er een betrouwbare basis wanneer een winkel geautomatiseerde paginatoegang tijdelijk blokkeert.

Een product verschijnt uitsluitend wanneer er een productfoto beschikbaar is en ten minste één aannemelijke maat uit XL, XXL/2XL of een passende Short/Tall-variant op voorraad is aangetroffen. Donkergroen en andere zeer donkere kleuren zijn toegestaan wanneer materiaal, kleurdiepte en overige bewijzen de kans op zichtbaar nat-droogcontrast voldoende beperken.

## Lokaal testen

```powershell
python -m pip install -r requirements.txt
python find-clothing.py
python select-clothing.py
python make-report.py
```
