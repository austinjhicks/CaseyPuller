# CaseyPuller Local Website

This is a tiny local web interface for running the two CaseyPuller scripts.

## Folder setup

Put these files together in the same project folder:

```text
CaseyPuller/
    app.py
    download_cafc_opinions.py
    search_pdf_watchlist_v2.py
    patsORparties.csv
    requirements.txt
    templates/
        index.html
```

The app will create/use:

```text
uploads/
cafc_opinions/
matches.csv
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Use

1. Upload the Federal Circuit `.eml` email.
2. Click **Download opinion PDFs**.
3. Make sure `patsORparties.csv` is in the same folder as `app.py`.
4. Click **Search opinions**.
5. Download `matches.csv`.

## Important note

A bare HTML file cannot run Python scripts directly. This uses Flask as a tiny local backend so the browser buttons can safely trigger the local Python scripts.
