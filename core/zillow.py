from apify_client import ApifyClient
from config.settings import APIFY_API_TOKEN

def get_zillow_infos(address: str):
    try:
        client = ApifyClient(APIFY_API_TOKEN)
        run_input = {"addresses": [address]}
        run = client.actor("ENK9p4RZHg0iVso52").call(run_input=run_input, logger=None)

        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            status = item["homeStatus"]
            zestimate = item['zestimate']
            homeType = item['homeType']
            propertyTypeDimension = item['propertyTypeDimension']
            isCurrentSignedInAgentResponsible = item['isCurrentSignedInAgentResponsible']
            lowest_zest = float(zestimate) - (float(zestimate) * float(item['zestimateLowPercent']) / 100)
            return lowest_zest, status, homeType, propertyTypeDimension, isCurrentSignedInAgentResponsible
    except Exception:
        return None