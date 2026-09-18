import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def assign_microclimates(df: pd.DataFrame, n_clusters: int = 5) -> pd.DataFrame:
    """
    Groups planting coordinates into microclimates based on environmental factors.
    Dynamically adjusts clusters if the number of points is less than n_clusters.
    """
    features = ['elevation', 'sunlight_hours', 'soil_ph', 'water_availability']
    X = df[features]

    # Dynamically adjust n_clusters if dataset has fewer points
    num_samples = len(df)
    effective_clusters = max(1, min(n_clusters, num_samples))

    if effective_clusters == 1:
        df['microclimate_zone'] = 0
        return df

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=effective_clusters, random_state=42, n_init=10)
    df['microclimate_zone'] = kmeans.fit_predict(X_scaled)

    return df