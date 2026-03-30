#!/bin/bash

# Script de déploiement basique pour le VPS

echo "Tirage des dernières modifications depuis Git..."
git pull origin main

echo "Installation des dépendances Python..."
# Décommenter la ligne suivante si un environnement virtuel est utilisé
# source venv/bin/activate
pip install -r requirements.txt

echo "Redémarrage du service systemd..."
sudo systemctl restart crypto_bot

echo "Statut du service :"
sudo systemctl status crypto_bot --no-pager

echo "Déploiement terminé !"
