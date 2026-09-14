# NoSQL Schema Inspector

## Overview

**NoSQL Schema Inspector** is an open-source web-based framework designed for the automatic discovery, visualization, security auditing, and continuous monitoring of document-oriented NoSQL databases.

The system provides a unified environment for analyzing semi-structured data stored in databases such as MongoDB, CouchDB, and Firebase Firestore. It automatically infers hidden schemas, generates interactive structural visualizations, performs rule-based security auditing, evaluates data quality via semantic profiling, and exports analysis reports in multiple formats.

Furthermore, the platform tracks database evolution by monitoring modifications in real-time and comparing snapshots to detect schema drift. It is implemented in Python using Streamlit, integrating interactive visualization libraries and AI-assisted analysis capabilities.

---

## Main Features

### Automatic Schema Inference

The framework recursively analyzes document collections to identify:

* Field names
* Data types
* Nested document structures
* Array contents
* Field occurrence frequency
* Structural variability across documents

### Interactive Schema Visualization

Discovered schemas are rendered as hierarchical treemaps using Plotly, enabling intuitive exploration of complex document structures through interactive visual analytics.

### Security Auditing Engine

The integrated auditing engine evaluates sampled data against ten predefined security rules, including:

* Plaintext credential exposure
* Personally identifiable information (PII) leakage
* NoSQL injection patterns
* Weak or deprecated hash usage
* Financial information exposure
* Missing audit metadata
* Insecure configuration patterns

The audit module generates:

* Vulnerability findings
* Severity classification
* Rule-based explanations
* A global security score ranging from 0 to 100

### Sensitive Data Masking

Values identified as sensitive are automatically masked before visualization or export in order to reduce accidental exposure during analysis.

### Report Generation

Analysis results can be exported in multiple formats:

* JSON
* CSV
* PDF

The generated reports summarize inferred schemas, detected vulnerabilities, and security evaluation results.

### Schema Drift Detection

Allows saving schema snapshots and comparing them over time to detect changes (added fields, removed fields, modified types).

### Data Quality (Semantic Profiling)

Evaluates the overall quality and completeness of the data, generating global wellness grades (from A to F).

### Real-Time Change Monitoring

Listens to database modifications live (Change Streams for MongoDB, Real-time listeners for Firestore) and updates the interface automatically.

### AI-Assisted Interpretation

The framework integrates a conversational assistant powered by Groq and LLaMA 3 models to assist users in:

* Understanding audit findings
* Interpreting schema structures
* Identifying remediation strategies
* Explaining detected vulnerabilities

### Multi-Database Support

The framework currently supports:

* MongoDB
* CouchDB
* Firebase Firestore

Its modular architecture allows the integration of additional NoSQL systems through the `BaseConnector` abstraction layer.

---

## System Requirements

* Python 3.11 or later
* pip or Conda package manager
* Windows, Linux, or macOS
* Access to a running NoSQL database instance
* Groq API key (optional, required only for the AI assistant)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/hibasb/NoSQL_Schema_inspector.git
cd NoSQL_Schema_inspector
```

### 2. Create a Virtual Environment

#### Linux/macOS

```bash
python -m venv venv
source venv/bin/activate
```

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Main dependencies include:

* streamlit
* pymongo
* firebase-admin
* requests
* pandas
* plotly
* reportlab
* groq
* python-dotenv

### 4. Configure Environment Variables

Create a `.env` file from the provided template:

```bash
cp .env.example .env
```

Add the Groq API key:

```env
GROQ_API_KEY=your_api_key_here
```

---

## Running the Application

Launch the Streamlit application:

```bash
streamlit run app.py
```

The application will be available at:

```text
http://localhost:8501
```

---

## Usage Workflow

1. Select the target database system from the sidebar.
2. Provide the connection URI or authentication credentials.
3. Connect to the database instance.
4. Run schema analysis to discover structures.
5. Evaluate data quality and completeness via the Semantic Profiler.
6. Explore the inferred schema and interactive visualizations.
7. Execute the security audit module.
8. Monitor database modifications live with the Real-Time Change Monitor.
9. Save schema snapshots and compare them over time to detect Schema Drift.
10. Export analysis reports in the desired format.

---

## Project Architecture

```text
NoSQL_Schema_inspector/
│
├── app.py
│   Main Streamlit application and orchestration layer
│
├── connectors/
│   Database connector implementations
│
├── schema_inferrer.py
│   Recursive schema inference engine
│
├── security_auditor.py
│   Rule-based security auditing engine
│
├── semantic_profiler.py
│   Data quality and completeness evaluation
│
├── realtime_monitor.py
│   Live database modifications listener
│
├── drift_detector.py
│   Schema snapshots and drift comparison
│
├── visualizer.py
│   Interactive visualization generation
│
├── exporter.py
│   JSON, CSV, and PDF report generation
│
├── chatbot.py
│   Groq/LLaMA 3 conversational assistant
│
├── requirements.txt
│   Project dependencies
│
├── .env.example
│   Environment variable template
│
└── README.md
```

---

## Screenshots

### Schema Visualization

<img width="724" height="342" alt="image" src="images\Schema_Visualization.png" />


### Security Audit Dashboard

<img width="727" height="343" alt="image" src="images\Security_Audit.png" />


### Schema Drift

<img width="727" height="343" alt="image" src="images\Schema_Drift.png" />


### Data Quality

<img width="727" height="343" alt="image" src="images\Data_Quality.png" />

---

## License
This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file for details.

---

## Research Citation

If you use this framework in academic research, please cite:

```bibtex
@article{hanine2026nosql,
  title   = {NoSQL Schema Inspector: An Automated Tool for Discovering, Visualizing, and Auditing Document Database Structures},
  author  = {Hanine Mohamed, Chokri Zahra, Sebban Hiba and Razzouk Majda},
  journal = {SoftwareX},
  year    = {2026}
}
```
**Archive:** [https://doi.org/10.5281/zenodo.20683271](https://doi.org/10.5281/zenodo.20683271)

---

## Authors

* Majda Razzouk - [@MajdaRAZZOUK](https://github.com/majdamija123)
* Zahra Chokri - [@ZahraCHOKRI](https://github.com/Zahra0706)
* Hiba Sebban - [@HibaSEBBAN](https://github.com/hibasb)

National School of Applied Sciences (ENSA)
Chouaib Doukkali University
El Jadida, Morocco

---

## Contact

For questions, feedback, or collaboration inquiries:

* [mrazzouk233@gmail.com](mailto:mrazzouk233@gmail.com)
* [zahraechokrii@gmail.com](mailto:zahraechokrii@gmail.com)
* [Hibasebban@gmail.com](mailto:Hibasebban@gmail.com)



