import subprocess
import time
from datetime import datetime, timedelta
from subprocess import PIPE
from typing import Optional

from django.db.models.query import prefetch_related_objects
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import urlencode

from common.myanimelist_user import MyAnimeListUser
from main.models import Anime, AnimeRecs, ImportQue, UserAnime

from .forms import NameForm

USE_CROSSREF = {
    "use_watching": "1",
    "use_completed": "2",
    "use_on_hold": "3",
    "use_dropped": "4",
    "use_plan_to_watch": "5",
}

DO_NOT_RETURN_CROSSREF = {
    "do_not_return_watching": "1",
    "do_not_return_completed": "2",
    "do_not_return_on_hold": "3",
    "do_not_return_dropped": "4",
    "do_not_return_plan_to_watch": "5",
}


def index(request: HttpRequest) -> HttpResponse:
    form = NameForm()
    return render(request, "main/index.html", {"form": form})


def status_in(form: NameForm, media_type: str) -> str:
    use_values = [value for key, value in USE_CROSSREF.items() if form.cleaned_data.get(key) == True]
    return f"""user_{media_type}.status IN ("{'", "'.join(use_values)}'")"""


def do_not_return_in(form: NameForm, media_type: str) -> str:
    do_not_return_values = [v for k, v in DO_NOT_RETURN_CROSSREF.items() if not form.cleaned_data.get(k)]
    # If anime/manga with a specific status are set to not be returned use a more complex query
    if do_not_return_values:
        return_string = '", "'.join(do_not_return_values)
        if form.cleaned_data.get("do_not_return_not_on_list"):
            return (
                f'AND (rec_user_{media_type}.status IS NULL or rec_user_{media_type}.status NOT IN ("{return_string}"))'
            )
        else:
            return f'AND (rec_user_{media_type}.status NOT IN ("{return_string}"))'

    # If all anime/manga are to be returned a simpler query can be used
    else:
        return ""


def select_score_rec(form: NameForm, media_type: str, user: MyAnimeListUser) -> str:
    recs_to_truncate = form.cleaned_data["ignore_recs_over"]
    # TODO: Technically not every query needs the IIF statement
    # TODO: Including it just makes things easier to read and write
    # TODO: Find a clean way to split this up better for faster queries
    select_rec_score_string = f"IIF({media_type}_recs.recommendations > {recs_to_truncate}, {recs_to_truncate}"
    # If popularity compensation is enabled use an extra math string to compensate
    # If popularity compensation is enabled use an extra math string to compensate
    if form.cleaned_data["popularity_compensation"]:
        math_string = f"({media_type}.popularity + rec_{media_type}.popularity)"
        select_rec_score_string += f".0 * {math_string}, {media_type}_recs.recommendations * {math_string}"
    else:
        select_rec_score_string += f", {media_type}_recs.recommendations"

    # If score compensation is enabled add it to the equation
    if form.cleaned_data["score_compensation"]:
        # If there is no score given for an anime just use the average score for compensation
        select_rec_score_string += (
            f" * IIF(user_{media_type}.score = 0, {user.model.average_anime_score}, user_{media_type}.score)"
        )

    # Close up the string
    select_rec_score_string += ")"
    return select_rec_score_string


def recs_string(form: NameForm, media_type: str) -> str:
    if (minimum_recs := form.cleaned_data["minimum_recs"]) != "1":
        return f"""INNER JOIN {media_type}_recs ON ({media_type}_recs.media_id = user_{media_type}.media_id AND {media_type}_recs.recommendations >= {minimum_recs})"""
    else:
        return f""" INNER JOIN {media_type}_recs ON ({media_type}_recs.media_id = user_{media_type}.media_id)"""


def join_media_if_needed(form: NameForm, media_type: str) -> str:
    if form.cleaned_data["popularity_compensation"]:
        return f"""INNER JOIN {media_type} ON ({media_type}.id = user_{media_type}.media_id) INNER JOIN {media_type} rec_anime ON (rec_{media_type}.id = {media_type}_recs.media_id)"""
    else:
        return ""


def json_response(request: HttpRequest) -> HttpResponse:
    form = NameForm(request.GET)
    # TODO: Make this an actual 404-like page
    if not form.is_valid():
        return HttpResponse("Invalid form")

    command: list[str] = ["out"]  # Start of command to run external programm
    media_type = form.cleaned_data["anime_or_manga"]
    user = MyAnimeListUser(form.cleaned_data["username"])

    # Building the SQL query by hand to make it as fast as possible
    # This is by far the slowest part of the website so it needs to be as fast as possible
    sql_command = f"""SELECT
                        {media_type}_recs.recommended_media_id,
                        SUM({select_score_rec(form, media_type, user)}) AS rec_score,
                        rec_user_{media_type}.status,
                        GROUP_CONCAT({media_type}_recs.media_id, CHAR(0x1F)) AS rec_ids,
                        GROUP_CONCAT({media_type}_recs.recommendations, CHAR(0x1F)) AS rec_counts

                    -- Start with all entries on the user's list
                    FROM user_{media_type}
                    
                    -- Get recommendations based on the media on the user's list
                    {recs_string(form, media_type)}

                    {join_media_if_needed(form, media_type)}

                    -- Must be a left join because not all entries will be on the uer's list
                    LEFT JOIN user_{media_type} rec_user_{media_type} ON ({media_type}_recs.recommended_media_id = rec_user_{media_type}.media_id AND rec_user_{media_type}.user_id = {user.model.id})

                    -- Only the specific media type for this user
                    WHERE ({status_in(form, media_type)} AND user_{media_type}.user_id = {user.model.id} {do_not_return_in(form, media_type)})
                    
                    GROUP BY {media_type}_recs.recommended_media_id
                    ORDER BY rec_score DESC
                    LIMIT {form.cleaned_data['number_of_results']}
                        """

    # Add sql command to the command list
    command = ["out", "-sql", sql_command]

    command.append("-debug")
    print(sql_command)
    jsoned = subprocess.run(command, stdout=PIPE, stderr=PIPE).stdout.decode()
    return HttpResponse(jsoned)


# TODO: Special response when dumb user disables all possible entries to use
def recommendations(request: HttpRequest) -> HttpResponse:
    form = NameForm(request.GET)
    # TODO: Make this an actual 404-like page
    if not form.is_valid():
        return HttpResponse("Invalid form")

    username = request.GET.get("username")
    user = MyAnimeListUser(username)
    if user.model_exists:
        # If there where missing anime entries last time the user visited the site update information
        if user.model.user_anime().count() != user.model.anime_count:
            modified_timestamp = datetime.now().astimezone()
            user.update_all(minimum_modified_timestamp=modified_timestamp)
    else:
        if not ImportQue.objects.filter(type="user", key=username).first():
            ImportQue.objects.create(
                type="user", key=username, minimum_modified_timestamp=datetime.now().astimezone() - timedelta(days=365)
            )

    context = {
        "user": user,
        "form": form,
    }

    request.GET.get("username")
    return render(request, "main/recommendations.html", context)


def update(request: HttpRequest, username: str) -> HttpResponse:
    form = NameForm(request.GET)
    # TODO: Make this an actual 404-like page
    if not form.is_valid():
        return HttpResponse("Invalid form")

    ImportQue.objects.get_or_create(
        type="user",
        key=username,
        defaults={
            "minimum_modified_timestamp": datetime.now().astimezone()  # Information was just imported, this value was used
        },
    )
    return redirect(f"/recommendations?{urlencode(form.data, doseq=True)}&redirect=update")


def delete(request: HttpRequest, username: str) -> HttpResponse:
    form = NameForm(request.GET)
    # TODO: Make this an actual 404-like page
    if not form.is_valid():
        return HttpResponse("Invalid form")

    user = MyAnimeListUser(username)
    user.model.delete()

    return redirect(f"/recommendations?{urlencode(form.data, doseq=True)}&redirect=delete")
