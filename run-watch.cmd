@echo off
rem Taeglicher Reddit-Digest (verteiler) - Scheduled Task 'Verteiler Watch Digest', morgens.
rem Ausgaben und Fehler landen im Log.
"C:\Users\giova\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\giova\verteiler\watch.py" >> "C:\Users\giova\verteiler\logs\watch-task.log" 2>&1
