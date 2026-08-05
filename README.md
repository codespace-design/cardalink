# CardaLink: Smart Cardamom Marketplace & Farm Intelligence Platform

CardaLink is a cloud-enabled digital platform designed to modernize the cardamom trading ecosystem in Idukki, Kerala by integrating farm management, digital marketplace services, live auction mechanisms, AI-driven plant health diagnostics, and an NLP agricultural assistant into a containerized web application.

- **GitHub Repository**: [https://github.com/codespace-design/cardalink](https://github.com/codespace-design/cardalink)
- **Tech Stack**: Python 3.14, Django 6.0, Django Ninja API, PostgreSQL 18, Redis, Docker, AWS ECR, Ansible.

---

## 👥 Team Architecture & Feature Distribution

| Team Member | Role | Django App Directory | Feature Branch |
| :--- | :--- | :--- | :--- |
| **Member 1 (Lead)** | Auth, RBAC & Infrastructure | `carda_link/users/` | `feature/gouri-auth-roles` |
| **Member 2** | Farm Management & Plant Health AI | `carda_link/estates/` | `feature/alex-estate-mgmt` |
| **Member 3** | Auction Engine & Bidding | `carda_link/auctions/` | `feature/sam-auction-engine` |
| **Member 4** | Invoicing & Payments | `carda_link/invoicing/` | `feature/priya-invoicing` |
| **Member 5** | AI Assistant & Analytics | `carda_link/assistant/` | `feature/rahul-analytics` |

---

## 🛠 Local Development & Commands

### 1. Clone Repository & Start Containers
```bash
git clone https://github.com/codespace-design/cardalink.git
cd cardalink

# Start local Docker environment using 'just'
just up
```

### 2. Basic Developer Commands (`justfile`)
- **`just build`**: Rebuild python container images.
- **`just up`**: Start up local environment in detached mode.
- **`just down`**: Stop running containers.
- **`just pytest`**: Run unit test suite inside container stack.
- **`just manage <cmd>`**: Run Django `manage.py` commands (e.g. `just manage makemigrations`).

---

## 🌿 Developer Branching & Git Workflow

1. Always branch off `main`:
   ```bash
   git checkout main && git pull origin main
   git checkout -b feature/<your-name>-<module-name>
   ```
2. Develop inside your assigned app folder (`carda_link/<app_name>/`).
3. Run tests locally before committing:
   ```bash
   just pytest
   ```
4. Push and open a Pull Request (PR) to `main`.
5. Automated CI will check linting and unit tests. Upon Lead approval, merge to `main`.

---

## 🚀 Automated CI/CD & Deployment Pipeline

- **GitHub Actions (`.github/workflows/ci-cd.yml`)**:
  - Automatically runs `ruff` linter and `pytest` on PRs and pushes to `main`.
  - Builds production Docker image and pushes tag to **AWS ECR**.
  - Triggers **Ansible Playbook** (`deploy/playbook.yml`) to deploy live to AWS EC2 instance.
