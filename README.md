# Patent Opinion Monitor

Patent Opinion Monitor is an open-source tool for tracking patent-related legal developments that may matter to specific patents, patent owners, accused infringers, applicants, or other interested parties.

## Quick Start

1. Download the latest release ZIP.
2. Extract the folder.
3. Double-click START_CASEYPULLER.bat or CaseyPuller.exe.
4. Open http://127.0.0.1:5000.
5. Upload a Federal Circuit `.eml` email.
6. Edit `patsORparties.csv`.
7. Click Search Opinions.

## Goal

The current goal is to let a user provide a list of patents, applications, parties, or companies, and then automatically monitor public legal sources for relevant updates.

The system will collect opinions and notices from sources such as:

* Federal Circuit docket emails
* USPTO Official Gazette materials
* PTAB decisions
* Reexamination materials
* Other patent-related public legal sources

The tool will then parse the collected materials to identify:

* Parties
* Patent numbers
* Application numbers
* Legal issues
* Procedural posture
* Outcome
* Relevance to the user's watch list

Relevant opinions and notices will be organized in a shared Google Drive folder and summarized for the user.

## Planned Workflow

1. User uploads or enters a watch list of patents, applications, parties, or companies.
2. The system collects new opinions, decisions, and notices from monitored sources.
3. The system extracts key metadata from each document.
4. The system compares the extracted information against the user's watch list.
5. Relevant documents are saved into a shared Google Drive folder.
6. The user receives a short update identifying the relevant opinions, patents, parties, and legal issues.

## Planned Features

* Patent and party watch lists
* Federal Circuit opinion monitoring
* PTAB and reexamination monitoring
* PDF and email ingestion
* Patent number extraction
* Party-name extraction
* Legal-issue classification
* Relevance scoring
* Google Drive organization
* User-facing update summaries

## Example Use Case

A user provides the following watch list:

* Patent No. 10,000,000
* ABC Technologies Inc.
* XYZ Medical Devices LLC

The system monitors new Federal Circuit and USPTO materials. If a new opinion discusses ABC Technologies or cites Patent No. 10,000,000, the tool saves the opinion, extracts the relevant metadata, and alerts the user with a short summary.

## Status

Early development.

The project is currently focused on building the ingestion, parsing, matching, and Google Drive organization workflow.

## License

This project is open source under the MIT License.
