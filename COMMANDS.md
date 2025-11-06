# Realtime Avatar Command Reference

## 🚀 Quick Commands

### Setup & Build
```bash
# Check environment
python3 scripts/check_environment.py

# Extract voice samples (first time only)
./scripts/extract_voice_samples.sh

# Build Docker images
./scripts/build_images.sh

# All-in-one setup
./scripts/setup_local.sh
```

### Start Services
```bash
# Start runtime (foreground)
docker compose up runtime

# Start runtime (background)
docker compose up -d runtime

# Start with evaluator
docker compose --profile evaluator up

# Start specific service
docker compose up evaluator
```

### Stop Services
```bash
# Stop all
docker compose down

# Stop and remove volumes
docker compose down -v

# Stop specific service
docker compose stop runtime
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Generate English video
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "language": "en"}'

# Generate Chinese video
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "你好世界", "language": "zh-cn"}'

# Generate Spanish video
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola mundo", "language": "es"}'

# Download generated video
curl http://localhost:8000/api/v1/videos/FILENAME.mp4 -o output.mp4

# List available images
curl http://localhost:8000/api/v1/assets/images

# List voice samples
curl http://localhost:8000/api/v1/assets/voice-samples
```

### Logs & Debugging
```bash
# View runtime logs
docker compose logs runtime

# Follow logs (live)
docker compose logs -f runtime

# View evaluator logs
docker compose logs evaluator

# View all logs
docker compose logs -f

# Enter runtime container
docker compose exec runtime bash

# Enter evaluator container
docker compose exec evaluator bash

# Check Python environment
docker compose exec runtime python --version
docker compose exec runtime pip list
```

### Evaluator
```bash
# Run all tests
docker compose --profile evaluator up evaluator

# Run evaluator only (if runtime already running)
docker compose up evaluator

# View results
ls -lh evaluator/outputs/

# View latest summary
cat evaluator/outputs/summary_report_*.json | jq .

# Count test results
ls evaluator/outputs/*.json | wc -l
```

### Development
```bash
# Rebuild after code changes
docker compose up --build runtime

# Rebuild specific service
docker compose build runtime

# Restart service
docker compose restart runtime

# View resource usage
docker stats

# Check container status
docker compose ps
```

### Cleanup
```bash
# Remove stopped containers
docker compose rm

# Clean up Docker system
docker system prune

# Clean up Docker system (aggressive)
docker system prune -a

# Remove all project containers
docker compose down --rmi all -v

# Clean evaluator outputs
rm -rf evaluator/outputs/*.json
rm -rf evaluator/outputs/*.mp4
```

### Testing Components
```bash
# Test TTS only
docker compose exec runtime python -c "
from models.tts import get_xtts_model
model = get_xtts_model()
model.initialize()
print('TTS ready!')
"

# Test avatar only
docker compose exec runtime python -c "
from models.avatar import get_avatar_model
model = get_avatar_model()
model.initialize()
print('Avatar ready!')
"

# Test full pipeline
docker compose exec runtime python -c "
from pipelines.phase1_script import Phase1Pipeline
pipeline = Phase1Pipeline()
pipeline.initialize()
print('Pipeline ready!')
"
```

### File Operations
```bash
# Check assets
ls -lh assets/images/
ls -lh assets/videos/
ls -lh assets/voice/reference_samples/

# Check project structure
find . -type f -name "*.py" | wc -l

# Count lines of code
find . -name "*.py" | xargs wc -l | tail -1

# Search code
grep -r "XTTS" runtime/

# Find large files
find . -type f -size +10M -exec ls -lh {} \;
```

### Git Operations
```bash
# Initialize git (if not done)
git init

# Check status
git status

# Add all files
git add .

# Commit
git commit -m "Initial Realtime Avatar Phase 1 implementation"

# Create .gitignore (already exists)
# See .gitignore file
```

### Environment
```bash
# Copy environment template
cp .env.example .env

# Edit environment
nano .env
# or
code .env

# View current config
cat .env

# Test config
docker compose config
```

### Monitoring
```bash
# Watch container CPU/Memory
watch docker stats

# Check disk usage
du -sh *

# Check model cache
docker compose exec runtime du -sh /root/.cache

# Check output directory
docker compose exec runtime ls -lh /tmp/realtime-avatar-output
```

### Backup
```bash
# Backup outputs
tar -czf outputs_backup_$(date +%Y%m%d).tar.gz evaluator/outputs/

# Backup assets
tar -czf assets_backup_$(date +%Y%m%d).tar.gz assets/

# Full project backup (exclude large files)
tar -czf realtime-avatar_backup_$(date +%Y%m%d).tar.gz \
  --exclude='node_modules' \
  --exclude='.git' \
  --exclude='*.mp4' \
  --exclude='*.mov' \
  .
```

### Performance Testing
```bash
# Time a single generation
time curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Quick test", "language": "en"}'

# Benchmark with Apache Bench (if installed)
ab -n 10 -c 1 -p request.json -T 'application/json' \
  http://localhost:8000/api/v1/generate
```

### Useful Aliases (Add to ~/.zshrc or ~/.bashrc)
```bash
# Realtime Avatar aliases
alias rtup='docker compose up runtime'
alias rtdown='docker compose down'
alias rtlogs='docker compose logs -f runtime'
alias rteval='docker compose --profile evaluator up evaluator'
alias rtbuild='./scripts/build_images.sh'
alias rtcheck='python3 scripts/check_environment.py'
alias rtexec='docker compose exec runtime bash'
```

## 🎯 Common Workflows

### First Time Setup
```bash
python3 scripts/check_environment.py
./scripts/extract_voice_samples.sh
./scripts/build_images.sh
docker compose up runtime
# Wait for models to download...
# Test in another terminal
```

### Daily Development
```bash
# Start
docker compose up -d runtime
docker compose logs -f runtime

# Make changes in runtime/
# Code auto-reloads

# Test
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "test", "language": "en"}'

# Stop
docker compose down
```

### Run Full Test Suite
```bash
docker compose up -d runtime
# Wait for ready
docker compose --profile evaluator up evaluator
# View results
ls -lh evaluator/outputs/
```

### Clean Restart
```bash
docker compose down -v
docker compose build --no-cache
docker compose up runtime
```

## 📖 Documentation Quick Links

- **Getting Started**: `GETTING_STARTED.md`
- **Development Guide**: `DEVELOPMENT.md`
- **Project Status**: `PROJECT_STATUS.md`
- **API Documentation**: `README.md` → API Usage section
- **Project Spec**: `PROJECT_SPEC.md`

## 🆘 Emergency Commands

```bash
# Container won't stop
docker compose kill
docker compose rm -f

# Out of disk space
docker system prune -a --volumes
docker volume prune

# Reset everything
docker compose down -v --rmi all
./scripts/build_images.sh
docker compose up runtime

# Check what's wrong
docker compose ps
docker compose logs --tail=100
docker inspect realtime-avatar-runtime
```
