import pytest


@pytest.mark.django_db
def test_reviewer_can_add_review(review_client, submission):
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': 1,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 1
    assert submission.reviews.first().score == 1
    assert submission.reviews.first().text == 'LGTM'
    response = review_client.get(submission.orga_urls.reviews, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_reviewer_can_add_review_with_redirect(review_client, submission):
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': 1,
            'text': 'LGTM',
            'show_next': '1',
        }
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_reviewer_can_add_review_without_score(review_client, submission):
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 1
    assert submission.reviews.first().score is None
    assert submission.reviews.first().text == 'LGTM'
    response = review_client.get(submission.orga_urls.reviews, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_reviewer_cannot_use_wrong_score(review_client, submission):
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': 100,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('score,expected', ((-1, False), (2, True)))
def test_reviewer_can_use_override_score(review_user, review_client, submission, score, expected):
    submission.event.settings.set('allow_override_votes', True)
    review_user.teams.update(review_override_votes=1)
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': score,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 1
    review = submission.reviews.first()
    assert review.score is None
    assert review.override_vote is expected


@pytest.mark.django_db
def test_reviewer_cannot_use_override_score_twice(review_user, review_client, submission, other_submission):
    from pretalx.submission.models import Review
    submission.event.settings.set('allow_override_votes', True)
    review_user.teams.update(review_override_votes=1)
    Review.objects.create(override_vote=True, user=review_user, submission=other_submission)
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': -1,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 0


@pytest.mark.django_db
def test_reviewer_without_rights_use_override_score(review_client, submission):
    submission.event.settings.set('allow_override_votes', True)
    response = review_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': -1,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 0


@pytest.mark.django_db
def test_reviewer_cannot_review_own_submission(review_user, review_client, submission):
    submission.speakers.add(review_user)
    submission.save()
    response = review_client.post(
        submission.orga_urls.reviews,
        data={
            'score': 100,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 0


@pytest.mark.django_db
def test_reviewer_cannot_review_accepted_submission(review_user, review_client, submission):
    submission.accept()
    response = review_client.post(
        submission.orga_urls.reviews,
        data={
            'score': 100,
            'text': 'LGTM',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert submission.reviews.count() == 0


@pytest.mark.django_db
def test_reviewer_can_edit_review(review_client, review, review_user):
    count = review.submission.reviews.count()
    assert review.user == review_user
    response = review_client.post(
        review.urls.base, follow=True,
        data={
            'score': 0,
            'text': 'My mistake.',
        }
    )
    review.refresh_from_db()
    assert response.status_code == 200
    assert review.submission.reviews.count() == count
    assert review.score == 0
    assert review.text == 'My mistake.'


@pytest.mark.django_db
def test_reviewer_cannot_edit_review_after_accept(review_client, review):
    review.submission.accept()
    response = review_client.post(
        review.urls.base, follow=True,
        data={
            'score': 0,
            'text': 'My mistake.',
        }
    )
    review.refresh_from_db()
    assert response.status_code == 200
    assert review.submission.reviews.count() == 1
    assert review.score != 0
    assert review.text != 'My mistake.'


@pytest.mark.django_db
def test_cannot_see_other_review_before_own(other_review_client, review):
    response = other_review_client.get(review.urls.base, follow=True)
    assert response.status_code == 200
    assert review.text not in response.content.decode()

    response = other_review_client.post(
        review.urls.base, follow=True,
        data={
            'score': 0,
            'text': 'My mistake.',
        }
    )
    review.refresh_from_db()
    assert response.status_code == 200
    assert review.submission.reviews.count() == 2
    assert review.score != 0
    assert review.text != 'My mistake.'
    assert review.text in response.content.decode()
    assert 'My mistake' in response.content.decode()


@pytest.mark.django_db
def test_can_see_review(review_client, review):
    response = review_client.get(review.urls.base, follow=True)
    assert response.status_code == 200
    assert review.text in response.content.decode()


@pytest.mark.django_db
def test_can_see_review_after_accept(review_client, review):
    review.submission.accept()
    response = review_client.get(review.urls.base, follow=True)
    assert response.status_code == 200
    assert review.text in response.content.decode()


@pytest.mark.django_db
def test_orga_cannot_see_review(orga_client, review):
    response = orga_client.get(review.urls.base, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_reviewer_can_see_dashboard(review_client, submission, review):
    response = review_client.get(submission.event.orga_urls.reviews)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_cannot_add_review(orga_client, submission):
    response = orga_client.post(
        submission.orga_urls.reviews, follow=True,
        data={
            'score': 1,
            'text': 'LGTM',
        }
    )
    assert response.status_code == 404
    assert submission.reviews.count() == 0
