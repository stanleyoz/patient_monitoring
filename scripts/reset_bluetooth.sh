#!/bin/bash

echo "Stopping all python processes..."
pkill -9 python3

echo "Stopping bluetooth service..."
sudo systemctl stop bluetooth

echo "Cleaning bluetooth cache..."
sudo rm -rf /var/lib/bluetooth/*

echo "Removing any stray bluetoothd processes..."
sudo pkill -9 bluetoothd

echo "Resetting bluetooth hardware..."
sudo hciconfig hci0 down
sleep 2
sudo hciconfig hci0 up
sleep 2

echo "Starting bluetooth service..."
sudo systemctl start bluetooth
sleep 3

echo "Checking bluetooth status..."
sudo systemctl status bluetooth
hciconfig

echo "Bluetooth reset complete. Wait 5 seconds before starting IMU collection..."
sleep 5
