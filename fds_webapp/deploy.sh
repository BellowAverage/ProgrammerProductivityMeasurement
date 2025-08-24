#!/bin/bash

# FDS Web Application Deployment Script
# Run this script on your Ubuntu server to deploy the application

set -e  # Exit on any error

echo "🚀 Starting FDS Web Application Deployment..."

# Configuration
PROJECT_NAME="fds_webapp"
PROJECT_DIR="/var/www/$PROJECT_NAME"
REPO_URL="https://github.com/BellowAverage/ProgrammerProductivityMeasurement.git"
PYTHON_VERSION="3.11"
DB_NAME="fds_webapp"
DB_USER="fds_user"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

print_status "Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib nginx redis-server \
    git curl wget unzip supervisor \
    build-essential libpq-dev libssl-dev libffi-dev \
    certbot python3-certbot-nginx

print_status "Creating project directory..."
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR

print_status "Cloning repository..."
if [ -d "$PROJECT_DIR/.git" ]; then
    cd $PROJECT_DIR
    git pull origin main
else
    git clone $REPO_URL $PROJECT_DIR
    cd $PROJECT_DIR
fi

# Navigate to the Django project directory
cd $PROJECT_DIR/fds_webapp

print_status "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

print_status "Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" || true
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD 'change_this_password';" || true
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';" || true
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';" || true
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'UTC';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" || true

print_status "Setting up environment variables..."
if [ ! -f .env ]; then
    cp env.example .env
    print_warning "Please edit .env file with your actual configuration values!"
    print_warning "Especially: SECRET_KEY, DB_PASSWORD, EMAIL settings, ALLOWED_HOSTS"
fi

print_status "Creating logs directory..."
mkdir -p logs
sudo mkdir -p /var/log/uwsgi
sudo chown www-data:www-data /var/log/uwsgi

print_status "Running Django migrations..."
python manage.py migrate --settings=fds_webapp.settings_production

print_status "Creating Django superuser..."
echo "Please create a superuser account:"
python manage.py createsuperuser --settings=fds_webapp.settings_production || true

print_status "Collecting static files..."
python manage.py collectstatic --noinput --settings=fds_webapp.settings_production

print_status "Creating example data..."
python manage.py create_example_analyses --settings=fds_webapp.settings_production || true
python manage.py create_parameter_presets --settings=fds_webapp.settings_production || true

print_status "Setting up file permissions..."
sudo chown -R www-data:www-data $PROJECT_DIR
sudo chmod -R 755 $PROJECT_DIR
sudo chmod -R 775 $PROJECT_DIR/fds_webapp/media
sudo chmod -R 775 $PROJECT_DIR/fds_webapp/logs

print_status "Installing systemd service..."
sudo cp fds_webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fds_webapp
sudo systemctl start fds_webapp

print_status "Configuring Nginx..."
sudo cp nginx_fds_webapp.conf /etc/nginx/sites-available/fds_webapp
sudo ln -sf /etc/nginx/sites-available/fds_webapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

print_status "Setting up SSL certificate..."
print_warning "Please run the following command to set up SSL (replace your-domain.com):"
echo "sudo certbot --nginx -d your-domain.com -d www.your-domain.com"

print_status "Setting up firewall..."
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable

print_status "✅ Deployment completed successfully!"
echo ""
echo "🔧 Next steps:"
echo "1. Edit /var/www/fds_webapp/fds_webapp/.env with your actual configuration"
echo "2. Update ALLOWED_HOSTS in .env with your domain name"
echo "3. Set up SSL certificate with certbot"
echo "4. Update Nginx configuration with your actual domain name"
echo "5. Restart services: sudo systemctl restart fds_webapp nginx"
echo ""
echo "📊 Your FDS Web Application should now be accessible at your domain!"
echo "🔐 Admin panel: https://your-domain.com/admin/"
echo "📝 Logs: /var/log/uwsgi/fds_webapp.log and /var/log/nginx/"
