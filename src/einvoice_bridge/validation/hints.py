"""Plain-German explanations for the rules small businesses trip over most.

The official rule texts are terse and mostly English. These hints say what
the rule means and what to change, in the words a bookkeeper would use.
"""

from __future__ import annotations

HINTS: dict[str, str] = {
    "XSD": (
        "Die Datei entspricht nicht dem XML-Schema (Aufbau, Reihenfolge oder Datentyp eines "
        "Elements ist falsch). Das liegt fast immer an der erzeugenden Software, nicht an den "
        "Rechnungsdaten. Weitere Regeln werden erst geprüft, wenn das Schema stimmt."
    ),
    "BR-01": "Die Spezifikationskennung (BT-24) fehlt. Sie sagt, nach welchem Standard die Rechnung erstellt wurde.",
    "BR-02": "Die Rechnungsnummer (BT-1) fehlt.",
    "BR-03": "Das Rechnungsdatum (BT-2) fehlt.",
    "BR-04": "Der Rechnungstyp (BT-3, z. B. 380 für Rechnung, 381 für Gutschrift) fehlt.",
    "BR-05": "Die Rechnungswährung (BT-5) fehlt.",
    "BR-06": "Der Name des Verkäufers (BT-27) fehlt.",
    "BR-07": "Der Name des Käufers (BT-44) fehlt.",
    "BR-08": "Die Anschrift des Verkäufers (BG-5) fehlt.",
    "BR-09": "Der Ländercode in der Anschrift des Verkäufers (BT-40) fehlt.",
    "BR-10": "Die Anschrift des Käufers (BG-8) fehlt.",
    "BR-11": "Der Ländercode in der Anschrift des Käufers (BT-55) fehlt.",
    "BR-16": "Die Rechnung braucht mindestens eine Rechnungsposition.",
    "BR-CO-10": (
        "Die Summe der Positionsbeträge (BT-106) stimmt nicht mit den einzelnen Positionen überein. "
        "Prüfen Sie Rundungen: jede Position wird auf zwei Nachkommastellen gerundet, dann summiert."
    ),
    "BR-CO-13": (
        "Der Nettobetrag der Rechnung (BT-109) muss Positionssumme minus Nachlässe plus Zuschläge sein."
    ),
    "BR-CO-15": "Der Bruttobetrag (BT-112) muss Nettobetrag (BT-109) plus Umsatzsteuer (BT-110) sein.",
    "BR-CO-16": (
        "Der Zahlbetrag (BT-115) muss Bruttobetrag minus bereits gezahlter Betrag (BT-113) "
        "plus Rundungsbetrag sein. Bei bereits bezahlten Rechnungen ist er 0."
    ),
    "BR-CO-17": (
        "Die Umsatzsteuer je Steuersatz (BT-117) muss Nettobetrag × Steuersatz sein "
        "(auf zwei Stellen gerundet, Toleranz eine Währungseinheit)."
    ),
    "BR-CO-25": (
        "Wenn ein Betrag offen ist, muss entweder ein Fälligkeitsdatum (BT-9) oder ein Text mit "
        "Zahlungsbedingungen (BT-20) angegeben werden."
    ),
    "BR-S-08": (
        "Für jeden Umsatzsteuersatz muss der Nettobetrag in der Steueraufschlüsselung der Summe "
        "der Positionen mit diesem Satz entsprechen."
    ),
    "BR-E-10": (
        "Bei steuerbefreiten Umsätzen (Kategorie E, z. B. Kleinunternehmer nach § 19 UStG) muss ein "
        "Befreiungsgrund angegeben werden, etwa „Kein Ausweis von Umsatzsteuer, da Kleinunternehmer "
        "gemäß § 19 UStG“."
    ),
    "BR-AE-02": (
        "Bei Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge, Kategorie AE) müssen die "
        "USt-IdNr. des Verkäufers und des Käufers angegeben werden."
    ),
    "BR-AE-10": (
        "Bei Reverse Charge (Kategorie AE) muss der Hinweis „Steuerschuldnerschaft des "
        "Leistungsempfängers“ als Befreiungsgrund angegeben werden."
    ),
    "BR-DE-1": (
        "Zahlungsanweisungen (BG-16) fehlen. Geben Sie die Zahlungsart an, bei Überweisung mit IBAN."
    ),
    "BR-DE-2": "Die Kontaktdaten des Verkäufers (BG-6: Name, Telefon, E-Mail) fehlen.",
    "BR-DE-3": "Der Ort des Verkäufers (BT-37) fehlt.",
    "BR-DE-4": "Die Postleitzahl des Verkäufers (BT-38) fehlt.",
    "BR-DE-5": "Ein Ansprechpartner oder eine Abteilung beim Verkäufer (BT-41) fehlt.",
    "BR-DE-6": "Die Telefonnummer des Verkäufers (BT-42) fehlt.",
    "BR-DE-7": "Die E-Mail-Adresse des Verkäufers (BT-43) fehlt.",
    "BR-DE-8": "Der Ort des Käufers (BT-52) fehlt. Ergänzen Sie die Rechnungsadresse des Kunden.",
    "BR-DE-9": "Die Postleitzahl des Käufers (BT-53) fehlt. Ergänzen Sie die Rechnungsadresse des Kunden.",
    "BR-DE-10": "Bei abweichender Lieferadresse fehlt der Ort (BT-77).",
    "BR-DE-11": "Bei abweichender Lieferadresse fehlt die Postleitzahl (BT-78).",
    "BR-DE-14": "Der Umsatzsteuersatz (BT-119) fehlt in der Steueraufschlüsselung.",
    "BR-DE-15": (
        "Die Käuferreferenz (BT-10) fehlt. Bei Behörden ist das die Leitweg-ID; bei Firmenkunden "
        "eine mit dem Kunden vereinbarte Referenz, z. B. Bestell- oder Kundennummer."
    ),
    "BR-DE-16": (
        "Es fehlt die USt-IdNr. (BT-31) oder Steuernummer (BT-32) des Verkäufers. Eine davon ist "
        "Pflicht, sobald Umsatzsteuer berechnet wird oder ein Befreiungsgrund gilt."
    ),
    "BR-DE-17": (
        "Der Rechnungstyp ist für XRechnung nicht zugelassen. Erlaubt sind u. a. 380 (Rechnung), "
        "381 (Gutschrift), 384 (Rechnungskorrektur), 389 (Selbstfakturierung) und 326 (Teilrechnung)."
    ),
    "BR-DE-18": (
        "Skonto-Angaben in den Zahlungsbedingungen müssen exakt dem Format "
        "#SKONTO#TAGE=14#PROZENT=2.00# folgen."
    ),
    "BR-DE-19": "Die IBAN für die Überweisung ist ungültig. Prüfen Sie sie auf Tippfehler.",
    "BR-DE-20": "Die IBAN für das Lastschriftmandat ist ungültig.",
    "BR-DE-21": (
        "Die Spezifikationskennung entspricht nicht XRechnung 3.0. Der Empfänger erwartet "
        "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0."
    ),
    "BR-DE-22": "Mehrere Anhänge haben denselben Dateinamen. Jeder Anhang braucht einen eindeutigen Namen.",
    "BR-DE-23-a": "Bei Zahlungsart Überweisung (30/58) müssen Überweisungsdaten mit IBAN angegeben werden.",
    "BR-DE-23-b": "Bei Zahlungsart Überweisung (30/58) dürfen keine Karten- oder Lastschriftdaten stehen.",
    "BR-DE-24-a": (
        "Bei Kartenzahlung (48/54/55) müssen Kartendaten angegeben werden, mindestens die letzten "
        "Ziffern der Kartennummer."
    ),
    "BR-DE-24-b": "Bei Kartenzahlung (48/54/55) dürfen keine Überweisungs- oder Lastschriftdaten stehen.",
    "BR-DE-25-a": "Bei Lastschrift (59) müssen Mandatsreferenz, Gläubiger-ID und IBAN des Zahlers angegeben werden.",
    "BR-DE-25-b": "Bei Lastschrift (59) dürfen keine Überweisungs- oder Kartendaten stehen.",
    "BR-DE-26": "Bei einer Rechnungskorrektur (384) sollte die ursprüngliche Rechnung referenziert werden.",
    "BR-DE-27": "Die Telefonnummer des Verkäufers sollte mindestens drei Ziffern enthalten.",
    "BR-DE-28": "Die E-Mail-Adresse des Verkäufers hat kein gültiges Format.",
    "PEPPOL-EN16931-R010": (
        "Die elektronische Adresse des Käufers (BT-49) fehlt. Für XRechnung 3.0 ist sie Pflicht; "
        "meist wird die E-Mail-Adresse mit Schema „EM“ verwendet."
    ),
    "PEPPOL-EN16931-R020": (
        "Die elektronische Adresse des Verkäufers (BT-34) fehlt. Für XRechnung 3.0 ist sie Pflicht; "
        "meist wird die E-Mail-Adresse mit Schema „EM“ verwendet."
    ),
    "PEPPOL-EN16931-R120": (
        "Der Positionsbetrag muss Menge × Einzelpreis (plus Zuschläge, minus Nachlässe) sein. "
        "Häufige Ursache: Rabatte wurden vom Betrag abgezogen, aber nicht als Nachlass ausgewiesen."
    ),
}


def hint_for(rule_id: str) -> str | None:
    return HINTS.get(rule_id)
