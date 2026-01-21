# GLS Label Service API - Specifiche Tecniche

## Endpoint e WSDL

- **Endpoint**: `https://labelservice.gls-italy.com/ilswebservice.asmx`
- **WSDL**: `https://labelservice.gls-italy.com/ilswebservice.asmx?WSDL`
- **Protocollo**: SOAP 1.1 / 1.2
- **Content-Type**: `text/xml; charset=utf-8`

---

## Autenticazione

Ogni richiesta deve includere le credenziali nel tag `<Info>`:

```xml
<Info>
  <SedeGls>XX</SedeGls>              <!-- Sigla sede GLS (2 char) -->
  <CodiceClienteGls>XXXXXX</CodiceClienteGls>  <!-- Codice cliente (6 cifre) -->
  <PasswordClienteGls>XXXXX</PasswordClienteGls>  <!-- Password -->
</Info>
```

---

## Metodi Principali

### 1. AddParcel

**Scopo**: Registra una o più spedizioni (max 400 per chiamata).

**Request**:
```xml
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <AddParcel xmlns="https://labelservice.gls-italy.com/">
      <XMLInfoParcel>
        <![CDATA[
        <Info>
          <SedeGls>YH</SedeGls>
          <CodiceClienteGls>074453</CodiceClienteGls>
          <PasswordClienteGls>password</PasswordClienteGls>
          <Parcel>
            <!-- Dati spedizione - vedi sezione Tag Parcel -->
          </Parcel>
          <!-- Altri Parcel... -->
        </Info>
        ]]>
      </XMLInfoParcel>
    </AddParcel>
  </soap:Body>
</soap:Envelope>
```

**Response**:
```xml
<Parcel>
  <NumeroSpedizione>123456789</NumeroSpedizione>
  <SiglaSedeDestino>MI</SiglaSedeDestino>
  <SiglaSedeMittente>YH</SiglaSedeMittente>
  <Esito>OK</Esito>
  <Bda>DOC001</Bda>
  <PDF>base64_encoded_pdf...</PDF>  <!-- Se GeneraPdf=4 -->
</Parcel>
```

---

### 2. CloseWorkDay

**Scopo**: Conferma tutte le spedizioni aperte di una sede.

**Request**:
```xml
<CloseWorkDay xmlns="https://labelservice.gls-italy.com/">
  <XMLInfoParcel>
    <![CDATA[
    <Info>
      <SedeGls>YH</SedeGls>
      <CodiceClienteGls>074453</CodiceClienteGls>
      <PasswordClienteGls>password</PasswordClienteGls>
    </Info>
    ]]>
  </XMLInfoParcel>
</CloseWorkDay>
```

---

### 3. CloseWorkDayByShipmentNumber

**Scopo**: Conferma spedizioni specifiche (più flessibile di CloseWorkDay).

**Request**:
```xml
<CloseWorkDayByShipmentNumber xmlns="https://labelservice.gls-italy.com/">
  <XMLInfoParcel>
    <![CDATA[
    <Info>
      <SedeGls>YH</SedeGls>
      <CodiceClienteGls>074453</CodiceClienteGls>
      <PasswordClienteGls>password</PasswordClienteGls>
      <Parcel>
        <NumeroSpedizione>123456789</NumeroSpedizione>
      </Parcel>
      <Parcel>
        <NumeroSpedizione>123456790</NumeroSpedizione>
      </Parcel>
    </Info>
    ]]>
  </XMLInfoParcel>
</CloseWorkDayByShipmentNumber>
```

---

### 4. GetPdfBySped

**Scopo**: Ottiene l'etichetta PDF per una spedizione.

**Request**:
```xml
<GetPdfBySped xmlns="https://labelservice.gls-italy.com/">
  <XMLInfoParcel>
    <![CDATA[
    <Info>
      <SedeGls>YH</SedeGls>
      <CodiceClienteGls>074453</CodiceClienteGls>
      <PasswordClienteGls>password</PasswordClienteGls>
      <Parcel>
        <NumeroSpedizione>123456789</NumeroSpedizione>
      </Parcel>
    </Info>
    ]]>
  </XMLInfoParcel>
</GetPdfBySped>
```

**Response**:
```xml
<Parcel>
  <PDF>base64_encoded_pdf...</PDF>
</Parcel>
```

---

### 5. ListSped

**Scopo**: Lista spedizioni degli ultimi 40 giorni.

**Request**:
```xml
<ListSped xmlns="https://labelservice.gls-italy.com/">
  <XMLInfoParcel>
    <![CDATA[
    <Info>
      <SedeGls>YH</SedeGls>
      <CodiceClienteGls>074453</CodiceClienteGls>
      <PasswordClienteGls>password</PasswordClienteGls>
    </Info>
    ]]>
  </XMLInfoParcel>
</ListSped>
```

**Response** (per ogni spedizione):
```xml
<Parcel>
  <NumeroSpedizione>123456789</NumeroSpedizione>
  <DataSpedizione>25/01/2025</DataSpedizione>
  <RagioneSociale>Mario Rossi</RagioneSociale>
  <Localita>Milano</Localita>
  <Provincia>MI</Provincia>
  <Zipcode>20121</Zipcode>
  <Bda>DOC001</Bda>
  <Stato>APERTO|CHIUSO</Stato>
</Parcel>
```

---

### 6. DeleteSped

**Scopo**: Cancella una spedizione (solo se stato APERTO).

**Request**:
```xml
<DeleteSped xmlns="https://labelservice.gls-italy.com/">
  <XMLInfoParcel>
    <![CDATA[
    <Info>
      <SedeGls>YH</SedeGls>
      <CodiceClienteGls>074453</CodiceClienteGls>
      <PasswordClienteGls>password</PasswordClienteGls>
      <Parcel>
        <NumeroSpedizione>123456789</NumeroSpedizione>
      </Parcel>
    </Info>
    ]]>
  </XMLInfoParcel>
</DeleteSped>
```

---

## Tag Parcel (AddParcel)

### Obbligatori

| Tag | Tipo | Lunghezza | Descrizione |
|-----|------|-----------|-------------|
| `<CodiceContrattoGls>` | String | 2 | Codice contratto |
| `<RagioneSociale>` | String | 35 | Nome destinatario |
| `<Indirizzo>` | String | 40 | Via e numero civico |
| `<Localita>` | String | 30 | Città |
| `<Zipcode>` | String | 5 | CAP (5 cifre) |
| `<Provincia>` | String | 2 | Sigla provincia |

### Opzionali (Comuni)

| Tag | Tipo | Lunghezza | Descrizione | Default |
|-----|------|-----------|-------------|---------|
| `<Colli>` | Integer | - | Numero colli | 1 |
| `<PesoReale>` | Decimal | - | Peso in kg | 1.0 |
| `<TipoPorto>` | String | 1 | F=Franco, A=Assegnato | F |
| `<TipoCollo>` | String | 1 | 0=Normale, 1=Busta, 2=Pallet | 0 |
| `<TipoSpedizione>` | String | 1 | N=Nazionale, E=Export | N |
| `<Bda>` | String | 14 | Riferimento mittente | |
| `<NoteSpedizione>` | String | 40 | Note per corriere | |
| `<Email>` | String | 70 | Email destinatario | |
| `<Cellulare1>` | String | 20 | Telefono destinatario | |
| `<GeneraPdf>` | Integer | - | 0=No, 4=PDF in risposta | 0 |

### Opzionali (Servizi Aggiuntivi)

| Tag | Tipo | Descrizione |
|-----|------|-------------|
| `<Contrassegno>` | Decimal | Importo contrassegno |
| `<ModalitaIncasso>` | String | CASH/ASSEGNO |
| `<TipoContrassegno>` | String | 0=Contante, 1=Assegno |
| `<ImportoAssicurato>` | Decimal | Valore assicurato |
| `<PersonaRiferimento>` | String | Nome contatto |
| `<SiglaCorriere>` | String | Corriere specifico |
| `<DataPrenotazioneConsenso>` | String | Data ritiro (DD/MM/YYYY) |
| `<FasceOrarie>` | String | Fascia oraria consegna |
| `<IdentPIN>` | String | PIN identificativo |

---

## Valori GeneraPdf

| Valore | Descrizione |
|--------|-------------|
| 0 | Non genera PDF |
| 1 | PDF formato A4 (1 etichetta) |
| 2 | PDF formato A4 (4 etichette) |
| 3 | PDF formato 10x10 |
| 4 | PDF formato 10x15 (consigliato) |

---

## Codici Errore

### Errori Autenticazione

| Codice | Messaggio | Causa |
|--------|-----------|-------|
| - | "Login non avvenuto" | Credenziali errate |
| - | "Sede non trovata" | SedeGls non valida |
| - | "Cliente non abilitato" | Cliente non attivo |

### Errori Dati

| Codice | Messaggio | Causa |
|--------|-----------|-------|
| - | "Località non conforme" | CAP/Comune non corrispondono |
| - | "CAP non valido" | Formato CAP errato |
| - | "Codice contratto non valido" | Contratto inesistente |
| - | "Bda già presente" | Riferimento duplicato |
| - | "Peso non valido" | Peso <= 0 o formato errato |

### Errori Operativi

| Codice | Messaggio | Causa |
|--------|-----------|-------|
| - | "Spedizione non trovata" | NumeroSpedizione inesistente |
| - | "Spedizione già chiusa" | Tentativo modifica su chiusa |
| - | "Max 400 Parcel" | Superato limite batch |

---

## Limiti e Vincoli

| Parametro | Limite |
|-----------|--------|
| Max Parcel per AddParcel | 400 |
| Max giorni per ListSped | 40 |
| Lunghezza RagioneSociale | 35 char |
| Lunghezza Indirizzo | 40 char |
| Lunghezza Localita | 30 char |
| Lunghezza NoteSpedizione | 40 char |
| Formato CAP | 5 cifre numeriche |
| Formato Provincia | 2 char maiuscole |
| Unicità Bda | Per sede/cliente |

---

## Stati Spedizione

| Stato | Descrizione |
|-------|-------------|
| APERTO | Spedizione creata, non confermata |
| CHIUSO | Spedizione confermata, pronta per ritiro |
| IN TRANSITO | Spedizione in viaggio |
| CONSEGNATO | Spedizione consegnata |
| GIACENZA | Spedizione in giacenza |

**Nota**: Solo le spedizioni in stato APERTO possono essere cancellate o modificate.

---

## Esempio Completo AddParcel

```xml
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <AddParcel xmlns="https://labelservice.gls-italy.com/">
      <XMLInfoParcel>
        <![CDATA[
        <Info>
          <SedeGls>YH</SedeGls>
          <CodiceClienteGls>074453</CodiceClienteGls>
          <PasswordClienteGls>mypassword</PasswordClienteGls>
          <Parcel>
            <CodiceContrattoGls>79</CodiceContrattoGls>
            <RagioneSociale>Mario Rossi</RagioneSociale>
            <Indirizzo>Via Dante, 120</Indirizzo>
            <Localita>Milano</Localita>
            <Zipcode>20121</Zipcode>
            <Provincia>MI</Provincia>
            <Colli>1</Colli>
            <PesoReale>1.5</PesoReale>
            <TipoPorto>F</TipoPorto>
            <TipoCollo>0</TipoCollo>
            <TipoSpedizione>N</TipoSpedizione>
            <GeneraPdf>4</GeneraPdf>
            <Bda>ORD-2025-001</Bda>
            <Email>mario.rossi@email.com</Email>
            <Cellulare1>3331234567</Cellulare1>
            <NoteSpedizione>Chiamare prima della consegna</NoteSpedizione>
          </Parcel>
        </Info>
        ]]>
      </XMLInfoParcel>
    </AddParcel>
  </soap:Body>
</soap:Envelope>
```

---

## Note Implementazione

1. **Bda univoco**: Generare automaticamente se non presente (es: `{timestamp}-{progressivo}`)

2. **Conferma obbligatoria**: Le spedizioni restano in stato APERTO per max 40 giorni se non confermate con CloseWorkDay

3. **Batch processing**: Per grandi volumi, dividere in batch da 400 Parcel max

4. **PDF etichette**: Usare `GeneraPdf=4` per ottenere il PDF in Base64 direttamente nella risposta

5. **Retry logic**: Implementare retry con backoff esponenziale per errori di rete

6. **Validazione preventiva**: Verificare lunghezza campi prima di inviare per evitare errori
