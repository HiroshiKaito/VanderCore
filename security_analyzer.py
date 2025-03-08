import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
import hashlib
import re

logger = logging.getLogger(__name__)

class SecurityAnalyzer:
    def __init__(self):
        self.security_events: List[Dict[str, Any]] = []
        self.suspicious_patterns: Dict[str, re.Pattern] = {
            'known_scam': re.compile(r'(?i)(scam|fake|free|airdrop|giveaway)'),
            'suspicious_chars': re.compile(r'[<>{}|\[\]`]'),
            'rapid_tx': re.compile(r'multiple_tx_\d+s'),
            'unusual_amounts': re.compile(r'unusual_amount_pattern')
        }

        # Sicherheits-Schwellenwerte
        self.thresholds = {
            'min_tx_interval': 60,  # Minimaler Abstand zwischen Transaktionen (Sekunden)
            'max_daily_tx': 50,     # Maximale Transaktionen pro Tag
            'suspicious_amount': 100 # Verdächtige Transaktionsgröße in SOL
        }

    def analyze_wallet_security(self, wallet_address: str, 
                             transaction_history: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """Analysiert die Sicherheit einer Wallet"""
        try:
            security_score = 100.0
            warnings = []

            # Analysiere Wallet-Adresse
            address_score, address_warnings = self._analyze_address(wallet_address)
            security_score *= address_score
            warnings.extend(address_warnings)

            # Analysiere Transaktionshistorie
            if transaction_history:
                history_score, history_warnings = self._analyze_transaction_history(transaction_history)
                security_score *= history_score
                warnings.extend(history_warnings)

            # Prüfe auf bekannte Angriffsmuster
            pattern_score, pattern_warnings = self._check_attack_patterns(wallet_address, transaction_history)
            security_score *= pattern_score
            warnings.extend(pattern_warnings)

            # Normalisiere den Score auf 0-100
            security_score = max(min(security_score, 100), 0)

            # Logge Sicherheitsereignis
            self.log_security_event('wallet_analysis', {
                'wallet': wallet_address,
                'score': security_score,
                'warnings': warnings
            })

            return security_score, warnings

        except Exception as e:
            logger.error(f"Fehler bei der Sicherheitsanalyse: {e}")
            return 0.0, ["Fehler bei der Sicherheitsanalyse"]

    def _check_attack_patterns(self, wallet_address: str, 
                            transaction_history: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """Prüft auf bekannte Angriffsmuster"""
        score = 1.0
        warnings = []

        try:
            # Prüfe auf Dust-Attacken
            recent_small_tx = [
                tx for tx in transaction_history
                if (datetime.now() - tx['timestamp']).total_seconds() < 3600
                and float(tx.get('amount', 0)) < 0.001
            ]

            if len(recent_small_tx) > 3:
                score *= 0.7
                warnings.append("⚠️ Mögliche Dust-Attacke erkannt")

            # Prüfe auf Rainbow-Table-Attacken
            if self._is_weak_address(wallet_address):
                score *= 0.8
                warnings.append("⚠️ Potenziell schwache Wallet-Adresse")

            # Prüfe auf Flash-Loan-Attacken
            if self._detect_flash_loan_pattern(transaction_history):
                score *= 0.6
                warnings.append("⚠️ Verdächtiges Flash-Loan-Muster")

            return score, warnings

        except Exception as e:
            logger.error(f"Fehler bei der Angriffsmuster-Analyse: {e}")
            return 0.5, ["Fehler bei der Angriffsmuster-Analyse"]

    def _is_weak_address(self, address: str) -> bool:
        """Prüft auf schwache Wallet-Adressen"""
        # Implementiere zusätzliche Prüfungen für schwache Adressen
        return False

    def _detect_flash_loan_pattern(self, history: List[Dict[str, Any]]) -> bool:
        """Erkennt Flash-Loan-Muster"""
        if not history:
            return False

        try:
            # Suche nach großen Ein- und Auszahlungen innerhalb kurzer Zeit
            for i in range(len(history) - 1):
                tx1 = history[i]
                tx2 = history[i + 1]

                time_diff = (tx2['timestamp'] - tx1['timestamp']).total_seconds()
                amount_diff = abs(float(tx1.get('amount', 0)) - float(tx2.get('amount', 0)))

                if time_diff < 60 and amount_diff > 1000:
                    return True

            return False

        except Exception as e:
            logger.error(f"Fehler bei der Flash-Loan-Erkennung: {e}")
            return False

    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Protokolliert ein Sicherheitsereignis"""
        try:
            event = {
                'timestamp': datetime.now(),
                'type': event_type,
                'details': details,
                'severity': self._calculate_severity(event_type, details)
            }

            self.security_events.append(event)

            # Log kritische Events sofort
            if event['severity'] >= 8:
                logger.warning(f"Kritisches Sicherheitsereignis: {event_type} - {details}")
            else:
                logger.info(f"Sicherheitsereignis: {event_type} - {details}")

        except Exception as e:
            logger.error(f"Fehler beim Protokollieren des Sicherheitsereignisses: {e}")

    def _calculate_severity(self, event_type: str, details: Dict[str, Any]) -> int:
        """Berechnet den Schweregrad eines Sicherheitsereignisses (1-10)"""
        try:
            base_severity = {
                'wallet_analysis': 5,
                'suspicious_activity': 7,
                'attack_detected': 9,
                'validation_failed': 6
            }.get(event_type, 5)

            # Erhöhe Schweregrad basierend auf Details
            if 'score' in details and details['score'] < 50:
                base_severity += 2

            if 'warnings' in details and len(details['warnings']) > 2:
                base_severity += 1

            return min(max(base_severity, 1), 10)

        except Exception as e:
            logger.error(f"Fehler bei der Schweregrad-Berechnung: {e}")
            return 5  # Default severity value in case of error: {e}")
            return 5


    def _analyze_address(self, address: str) -> Tuple[float, List[str]]:
        """Analysiert die Sicherheit einer Wallet-Adresse"""
        score = 1.0
        warnings = []
        
        try:
            # Überprüfe Adressformat
            if not self._is_valid_solana_address(address):
                score *= 0.5
                warnings.append("⚠️ Ungewöhnliches Adressformat")
            
            # Überprüfe auf bekannte Muster
            for pattern_name, pattern in self.suspicious_patterns.items():
                if pattern.search(address):
                    score *= 0.7
                    warnings.append(f"⚠️ Verdächtiges Muster gefunden: {pattern_name}")
            
            return score, warnings
            
        except Exception as e:
            logger.error(f"Fehler bei der Adressanalyse: {e}")
            return 0.5, ["Fehler bei der Adressanalyse"]

    def _analyze_transaction_history(self, 
                                   history: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """Analysiert die Transaktionshistorie auf Sicherheitsrisiken"""
        score = 1.0
        warnings = []
        
        try:
            recent_transactions = [tx for tx in history 
                                 if datetime.now() - tx['timestamp'] < timedelta(hours=24)]
            
            # Überprüfe auf häufige kleine Transaktionen (mögl. Dust-Attacke)
            small_tx_count = len([tx for tx in recent_transactions 
                                if float(tx.get('amount', 0)) < 0.01])
            if small_tx_count > 5:
                score *= 0.8
                warnings.append("⚠️ Viele kleine Transaktionen - Mögliche Dust-Attacke")
            
            # Überprüfe auf ungewöhnliche Aktivitätszeiten
            night_tx_count = len([tx for tx in recent_transactions 
                                if tx['timestamp'].hour in range(1, 5)])
            if night_tx_count > 3:
                score *= 0.9
                warnings.append("⚠️ Ungewöhnliche Aktivitätszeiten")
            
            # Überprüfe auf schnelle aufeinanderfolgende Transaktionen
            if len(recent_transactions) > 10:
                score *= 0.9
                warnings.append("⚠️ Hohe Transaktionsfrequenz")
            
            return score, warnings
            
        except Exception as e:
            logger.error(f"Fehler bei der Transaktionshistorienanalyse: {e}")
            return 0.5, ["Fehler bei der Transaktionshistorienanalyse"]
    
    def _is_valid_solana_address(self, address: str) -> bool:
        """Überprüft, ob eine Adresse dem Solana-Format entspricht"""
        try:
            # Grundlegende Solana-Adressvalidierung
            if not address or len(address) != 44:
                return False
                
            # Überprüfe Base58-Format
            try:
                int(address, 16)
                return True
            except ValueError:
                return False
                
        except Exception as e:
            logger.error(f"Fehler bei der Adressvalidierung: {e}")
            return False
            
    def get_security_summary(self) -> Dict[str, Any]:
        """Erstellt eine Zusammenfassung der Sicherheitsereignisse"""
        try:
            recent_events = [event for event in self.security_events 
                           if datetime.now() - event['timestamp'] < timedelta(days=1)]
            
            return {
                'total_events': len(recent_events),
                'event_types': {event['type']: len([e for e in recent_events 
                                                  if e['type'] == event['type']])
                              for event in recent_events},
                'last_event': recent_events[-1] if recent_events else None
            }
            
        except Exception as e:
            logger.error(f"Fehler bei der Erstellung der Sicherheitszusammenfassung: {e}")
            return {}