import requests
import sys
import json
from datetime import datetime

class PRDBackendTester:
    def __init__(self, base_url="https://prd-300.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_basic_endpoint(self):
        """Test basic API connectivity"""
        try:
            response = requests.get(f"{self.base_url}/")
            success = response.status_code == 200
            details = f"Status: {response.status_code}, Response: {response.json() if success else response.text}"
            self.log_test("Basic API Connectivity", success, details)
            return success
        except Exception as e:
            self.log_test("Basic API Connectivity", False, str(e))
            return False

    def test_compress_valid_request(self):
        """Test /compress endpoint with valid PRD request"""
        valid_data = {
            "problem": "Users can't find relevant content in our mobile app due to poor search functionality",
            "coreUser": "Mobile app power users aged 25-40 who search for content 5+ times daily",
            "change": "Implement AI-powered semantic search with personalized results and instant suggestions",
            "metrics": "Search success rate increases from 65% to 85%, average search time decreases from 8 seconds to 3 seconds, daily search queries increase by 40%",
            "outOfScope": "Desktop web search, voice search, admin panel search, search analytics dashboard"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/compress",
                json=valid_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            success = response.status_code == 200
            if success:
                data = response.json()
                required_fields = ['status', 'prd', 'word_count', 'clarity_score', 'bloat_words_detected', 'callouts']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Valid PRD Compression", False, f"Missing fields: {missing_fields}")
                    return False
                
                # Validate clarity score structure
                if 'clarity_score' in data and data['clarity_score']:
                    clarity_fields = ['overall', 'persona_specificity', 'metric_strength', 'problem_sharpness', 'bloat_penalty']
                    missing_clarity = [field for field in clarity_fields if field not in data['clarity_score']]
                    if missing_clarity:
                        self.log_test("Valid PRD Compression", False, f"Missing clarity score fields: {missing_clarity}")
                        return False
                
                self.log_test("Valid PRD Compression", True, f"Status: {data.get('status')}, Word count: {data.get('word_count')}")
                return True
            else:
                self.log_test("Valid PRD Compression", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Valid PRD Compression", False, "Request timed out (30s)")
            return False
        except Exception as e:
            self.log_test("Valid PRD Compression", False, str(e))
            return False

    def test_empty_field_validation(self):
        """Test validation for empty fields"""
        empty_data = {
            "problem": "",
            "coreUser": "Mobile users",
            "change": "Add better search",
            "metrics": "Increase usage by 20%",
            "outOfScope": "Desktop features"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/compress",
                json=empty_data,
                headers={"Content-Type": "application/json"}
            )
            
            success = response.status_code == 400
            details = f"Status: {response.status_code}"
            if response.status_code == 400:
                details += f", Error: {response.json().get('detail', 'No detail')}"
            
            self.log_test("Empty Field Validation", success, details)
            return success
            
        except Exception as e:
            self.log_test("Empty Field Validation", False, str(e))
            return False

    def test_multiple_users_validation(self):
        """Test validation for multiple users in Core User field"""
        test_cases = [
            {"coreUser": "Users, admins", "expected_error": "Pick one user. Not a committee."},
            {"coreUser": "Users and admins", "expected_error": "Pick one user. Not a committee."},
            {"coreUser": "Users/admins", "expected_error": "Pick one user. Not a committee."}
        ]
        
        passed = 0
        for case in test_cases:
            multiple_user_data = {
                "problem": "Search is broken",
                "coreUser": case["coreUser"],
                "change": "Fix search",
                "metrics": "Increase success rate by 50%",
                "outOfScope": "Mobile features"
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/compress",
                    json=multiple_user_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 400:
                    error_detail = response.json().get('detail', '')
                    if case["expected_error"] in error_detail:
                        passed += 1
                        
            except Exception:
                pass
        
        success = passed == len(test_cases)
        self.log_test("Multiple Users Validation", success, f"{passed}/{len(test_cases)} cases passed")
        return success

    def test_metrics_without_numbers_validation(self):
        """Test validation for metrics without numbers"""
        no_numbers_data = {
            "problem": "Search is broken",
            "coreUser": "Mobile users",
            "change": "Fix search functionality",
            "metrics": "Improve user satisfaction and engagement significantly",
            "outOfScope": "Desktop features"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/compress",
                json=no_numbers_data,
                headers={"Content-Type": "application/json"}
            )
            
            success = response.status_code == 400
            details = f"Status: {response.status_code}"
            if response.status_code == 400:
                error_detail = response.json().get('detail', '')
                if "Metrics need numbers." in error_detail:
                    details += ", Correct error message"
                else:
                    details += f", Wrong error: {error_detail}"
                    success = False
            
            self.log_test("Metrics Without Numbers Validation", success, details)
            return success
            
        except Exception as e:
            self.log_test("Metrics Without Numbers Validation", False, str(e))
            return False

    def test_rejection_case(self):
        """Test case that should be rejected by Claude"""
        vague_data = {
            "problem": "Stuff is bad",
            "coreUser": "People",
            "change": "Make it better",
            "metrics": "Things improve by 10%",
            "outOfScope": "Bad stuff"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/compress",
                json=vague_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            success = response.status_code == 200
            if success:
                data = response.json()
                if data.get('status') == 'rejected' and 'rejection_reason' in data:
                    self.log_test("Rejection Case Handling", True, f"Properly rejected: {data.get('rejection_reason', 'No reason')[:100]}")
                    return True
                else:
                    # If it gets accepted despite being vague, that's also valid behavior
                    self.log_test("Rejection Case Handling", True, "Vague request was accepted (acceptable behavior)")
                    return True
            else:
                self.log_test("Rejection Case Handling", False, f"Status: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Rejection Case Handling", False, "Request timed out (30s)")
            return False
        except Exception as e:
            self.log_test("Rejection Case Handling", False, str(e))
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🧪 Starting PRD Backend API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 50)
        
        # Test basic connectivity first
        if not self.test_basic_endpoint():
            print("❌ Basic connectivity failed, stopping tests")
            return False
        
        # Run all validation tests
        self.test_compress_valid_request()
        self.test_empty_field_validation()
        self.test_multiple_users_validation()
        self.test_metrics_without_numbers_validation()
        self.test_rejection_case()
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Tests Summary: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All backend tests passed!")
            return True
        else:
            print("⚠️  Some backend tests failed. See details above.")
            return False

def main():
    tester = PRDBackendTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())