# 🚀 FDS Web Application - Production Deployment Guide

This guide provides step-by-step instructions for deploying the Fair Developer Score (FDS) Web Application on an Ubuntu server using Django, uWSGI, Nginx, and PostgreSQL.

## 📋 Prerequisites

- Ubuntu 20.04+ server with sudo privileges
- Domain name pointing to your server (optional but recommended)
- At least 2GB RAM and 20GB storage
- Basic knowledge of Linux command line

## 🛠️ Quick Deployment (Automated)

### Option 1: Automated Deployment Script

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BellowAverage/ProgrammerProductivityMeasurement.git
   cd ProgrammerProductivityMeasurement/fds_webapp
   ```

2. **Run the deployment script:**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

3. **Follow the prompts and complete the post-deployment steps below.**

## 🔧 Manual Deployment (Step-by-Step)

### Step 1: System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib nginx redis-server \
    git curl wget unzip supervisor \
    build-essential libpq-dev libssl-dev libffi-dev \
    certbot python3-certbot-nginx
```

### Step 2: Database Setup

```bash
# Switch to postgres user and create database
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE fds_webapp;
CREATE USER fds_user WITH PASSWORD 'your_secure_password_here';
ALTER ROLE fds_user SET client_encoding TO 'utf8';
ALTER ROLE fds_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE fds_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE fds_webapp TO fds_user;
\q
```

### Step 3: Application Setup

```bash
# Create project directory
sudo mkdir -p /var/www/fds_webapp
sudo chown $USER:$USER /var/www/fds_webapp

# Clone repository
git clone https://github.com/BellowAverage/ProgrammerProductivityMeasurement.git /var/www/fds_webapp
cd /var/www/fds_webapp/fds_webapp

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Environment Configuration

```bash
# Copy environment template
cp env.example .env

# Edit environment variables
nano .env
```

**Required .env configuration:**
```env
SECRET_KEY=your-super-secret-django-key-here-generate-a-new-one
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,your-server-ip

DB_NAME=fds_webapp
DB_USER=fds_user
DB_PASSWORD=your_secure_password_here
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@your-domain.com

REDIS_URL=redis://127.0.0.1:6379/1
```

### Step 5: Django Setup

```bash
# Run migrations
python manage.py migrate --settings=fds_webapp.settings_production

# Create superuser
python manage.py createsuperuser --settings=fds_webapp.settings_production

# Collect static files
python manage.py collectstatic --noinput --settings=fds_webapp.settings_production

# Create example data
python manage.py create_example_analyses --settings=fds_webapp.settings_production
python manage.py create_parameter_presets --settings=fds_webapp.settings_production

# Create logs directory
mkdir -p logs
sudo mkdir -p /var/log/uwsgi
sudo chown www-data:www-data /var/log/uwsgi
```

### Step 6: uWSGI Configuration

```bash
# Test uWSGI
uwsgi --ini uwsgi.ini

# Install systemd service
sudo cp fds_webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fds_webapp
sudo systemctl start fds_webapp

# Check status
sudo systemctl status fds_webapp
```

### Step 7: Nginx Configuration

```bash
# Copy Nginx configuration
sudo cp nginx_fds_webapp.conf /etc/nginx/sites-available/fds_webapp

# Update domain name in the configuration
sudo nano /etc/nginx/sites-available/fds_webapp
# Replace 'your-domain.com' with your actual domain

# Enable site
sudo ln -sf /etc/nginx/sites-available/fds_webapp /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Step 8: SSL Certificate (Let's Encrypt)

```bash
# Install SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Step 9: Firewall Setup

```bash
# Configure UFW firewall
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable

# Check status
sudo ufw status
```

### Step 10: File Permissions

```bash
# Set proper permissions
sudo chown -R www-data:www-data /var/www/fds_webapp
sudo chmod -R 755 /var/www/fds_webapp
sudo chmod -R 775 /var/www/fds_webapp/fds_webapp/media
sudo chmod -R 775 /var/www/fds_webapp/fds_webapp/logs
```

## 🔍 Post-Deployment Verification

### Check Services Status

```bash
# Check all services
sudo systemctl status fds_webapp
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server

# Check logs
sudo tail -f /var/log/uwsgi/fds_webapp.log
sudo tail -f /var/log/nginx/fds_webapp_error.log
```

### Test Application

1. **Visit your domain:** `https://your-domain.com`
2. **Admin panel:** `https://your-domain.com/admin/`
3. **Register a test user:** `https://your-domain.com/auth/register/`
4. **Run an analysis:** Create and test an FDS analysis

## 🔧 Maintenance Commands

### Update Application

```bash
cd /var/www/fds_webapp
git pull origin main
cd fds_webapp
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --settings=fds_webapp.settings_production
python manage.py collectstatic --noinput --settings=fds_webapp.settings_production
sudo systemctl restart fds_webapp
```

### Backup Database

```bash
# Create backup
sudo -u postgres pg_dump fds_webapp > fds_webapp_backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
sudo -u postgres psql fds_webapp < fds_webapp_backup_YYYYMMDD_HHMMSS.sql
```

### Monitor Logs

```bash
# Application logs
sudo tail -f /var/log/uwsgi/fds_webapp.log

# Nginx logs
sudo tail -f /var/log/nginx/fds_webapp_access.log
sudo tail -f /var/log/nginx/fds_webapp_error.log

# System logs
sudo journalctl -u fds_webapp -f
```

## 🚨 Troubleshooting

### Common Issues

1. **502 Bad Gateway:**
   - Check uWSGI service: `sudo systemctl status fds_webapp`
   - Check socket permissions: `ls -la /var/www/fds_webapp/fds_webapp.sock`

2. **Static files not loading:**
   - Run: `python manage.py collectstatic --settings=fds_webapp.settings_production`
   - Check Nginx configuration for static file paths

3. **Database connection errors:**
   - Verify PostgreSQL is running: `sudo systemctl status postgresql`
   - Check database credentials in `.env` file

4. **Permission denied errors:**
   - Reset permissions: `sudo chown -R www-data:www-data /var/www/fds_webapp`

### Performance Optimization

1. **Enable Redis caching:**
   ```bash
   sudo systemctl enable redis-server
   sudo systemctl start redis-server
   ```

2. **Optimize uWSGI workers:**
   - Edit `uwsgi.ini` and adjust `processes` based on CPU cores
   - Monitor memory usage and adjust `reload-on-rss`

3. **Database optimization:**
   ```sql
   -- Connect to PostgreSQL and run:
   ANALYZE;
   VACUUM;
   ```

## 📊 Monitoring and Alerts

### Set up log rotation

```bash
sudo nano /etc/logrotate.d/fds_webapp
```

Add:
```
/var/log/uwsgi/fds_webapp.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload fds_webapp
    endscript
}
```

## 🔐 Security Checklist

- [ ] Changed default SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configured proper ALLOWED_HOSTS
- [ ] Set up SSL certificate
- [ ] Enabled firewall (UFW)
- [ ] Set strong database passwords
- [ ] Configured secure session cookies
- [ ] Set up regular backups
- [ ] Monitor logs for suspicious activity

## 📞 Support

If you encounter issues during deployment:

1. Check the troubleshooting section above
2. Review application logs
3. Verify all configuration files
4. Ensure all services are running
5. Check firewall and network settings

## 🎉 Success!

Your FDS Web Application should now be running at:
- **Main site:** `https://your-domain.com`
- **Admin panel:** `https://your-domain.com/admin/`

The application includes:
- ✅ User registration and authentication
- ✅ GitHub repository analysis
- ✅ Fair Developer Score calculations
- ✅ Interactive dashboards and visualizations
- ✅ Parameter configuration system
- ✅ Example analyses for demonstration
