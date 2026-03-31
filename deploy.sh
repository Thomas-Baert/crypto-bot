#!/bin/bash

# Script de déploiement basique pour le VPS

echo "Installation des dépendances Python..."
# Décommenter la ligne suivante si un environnement virtuel est utilisé
# source venv/bin/activate
pip install -r requirements.txt --break-system-packages

echo "Redémarrage du bot dans la session screen 'cryptobot'..."

# 1. Envoie "Ctrl+C" au terminal virtuel du screen pour arrêter l'exécution actuelle du main.py
screen -S cryptobot -X stuff $'\003'

# 2. Petite pause pour laisser le temps au script de fermer proprement la base de données
sleep 2

# 3. Relance la commande pour allumer le bot
screen -S cryptobot -X stuff "python3 main.py"$'\n'

echo "Déploiement terminé ! Tu peux vérifier les logs à tout moment avec :"
echo "screen -r cryptobot"
