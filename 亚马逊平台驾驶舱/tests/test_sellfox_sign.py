from app.clients.sellfox import SellfoxClient


def test_sign_stable_example():
    # Matches official doc structure (not the exact sample secret output)
    query, sig = SellfoxClient.sign(
        access_token="d20d9d20-5db0-429a-8390-3694265e297c",
        client_id="1111111",
        client_secret="fde212ff-588a-11ef-b1d4-0c42a1eda3d9",
        url_path="/openapi/api/commodity/pageList.json",
        timestamp=1668153260508,
        nonce=888,
    )
    assert query["sign"] == sig
    assert len(sig) == 64
    assert query["timestamp"] == "1668153260508"
    assert query["nonce"] == "888"
    # Official sample signature
    assert (
        sig
        == "57bcbd213461d47e99e9b781c11f3fb37937127824272a30b95ddb5cbfea881e"
    )
