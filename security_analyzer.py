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
            'suspicious_chars': re.compile(r'[<>{}|\[\]`]')
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
            
            # Normalisiere den Score auf 0-100
            security_score = max(min(security_score, 100), 0)
            
            return security_score, warnings
            
        except Exception as e:
            logger.error(f"Fehler bei der Sicherheitsanalyse: {e}")
            return 0.0, ["Fehler bei der Sicherheitsanalyse"]
            
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
            
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Protokolliert ein Sicherheitsereignis"""
        try:
            event = {
                'timestamp': datetime.now(),
                'type': event_type,
                'details': details
            }
            self.security_events.append(event)
            logger.warning(f"Sicherheitsereignis: {event_type} - {details}")
            
        except Exception as e:
            logger.error(f"Fehler beim Protokollieren des Sicherheitsereignisses: {e}")
            
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
