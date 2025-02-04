import requests

class OpenEdxAPI:
    def __init__(self, base_url, client_id, client_secret):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self.get_access_token()

    def get_access_token(self):
        url = f"{self.base_url}/oauth2/access_token/"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json().get('access_token')

    def get_courses(self):
        url = f"{self.base_url}/api/courses/v1/courses/"
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

# Example usage:
# api = OpenEdxAPI(base_url='https://openedx.example.com', client_id='your_client_id', client_secret='your_client_secret')
# courses = api.get_courses()
# print(courses)