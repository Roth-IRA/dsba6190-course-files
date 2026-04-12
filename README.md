# DSBA 6190 — Cloud Computing for Data Analytics

Course materials for DSBA 6190 at UNC Charlotte (Spring/Fall 2026).

## Contents

### Unit 3: Machine Learning

| Folder | Description |
|---|---|
| `Unit3-ML/data/` | Datasets for the Charlotte Restaurant ML Lab |
| `Unit3-ML/notebooks/` | Jupyter notebooks for hands-on exercises |

**Datasets:**
- `charlotte_restaurants.csv` — Restaurant metadata (name, location, cuisine, ratings)
- `charlotte_reviews.csv` — Customer review text and sentiment data
- `neighborhoods.json` — Charlotte neighborhood geographic data

**Notebooks:**
- `Part1_CLT_Restaurant_ML.ipynb` — Machine Learning with restaurant data
- `Part2_CLT_GenAI_PromptEng.ipynb` — Generative AI and prompt engineering

### Unit 4: DevOps

| Folder | Description |
|---|---|
| `Unit4-DevOps/lab/starters/pipeline/` | Terraform starter files for the CI/CD pipeline lab |
| `Unit4-DevOps/lab/starters/app/` | CloudFormation SAM templates for the serverless app |

**Starter Files (Pipeline):**
- `main.tf` — Terraform configuration for the DevOps pipeline
- `variables.tf` — Input variables
- `outputs.tf` — Output definitions
- `lambda/pipeline.py` — Lambda function for pipeline automation

**Starter Files (App):**
- `template.yaml` — SAM template for the serverless application
- `template_with_security.yaml` — Extended template with security verification

## Usage

Clone or download this repository, then follow the instructions in your lab manual.

```bash
git clone https://github.com/fraziersmith/dsba6190-course-files.git
```

## Instructor

Dr. Frazier Smith — fsmith28@charlotte.edu
