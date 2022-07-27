import subprocess
from datetime import datetime
from subprocess import PIPE

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from common.myanimelist_user import MyAnimeListUser
from main.models import ImportQue

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


def json_response(request: HttpRequest) -> HttpResponse:
    form = NameForm(request.GET)
    # TODO: Make this an actual 404-like page
    if not form.is_valid():
        return HttpResponse("Invalid form")

    command: list[str] = ["out"]
    user = MyAnimeListUser(form.cleaned_data["username"])

    use_values = [value for key, value in USE_CROSSREF.items() if form.cleaned_data.get(key) == True]
    status_in = f"""user_anime.status IN ("{'", "'.join(use_values)}'")"""

    do_not_return_values = [v for k, v in DO_NOT_RETURN_CROSSREF.items() if not form.cleaned_data.get(k)]
    # If anime/manga with a specific status are set to not be returned use a more complex query
    if do_not_return_values:
        return_string = '", "'.join(do_not_return_values)
        if form.cleaned_data.get("do_not_return_not_on_list"):
            return_string = f'AND (rec_user_anime.status IS NULL or rec_user_anime.status NOT IN ("{return_string}"))'
        else:
            return_string = f'AND (rec_user_anime.status NOT IN ("{return_string}"))'

    # If all anime/manga are to be returned a simpler query can be used
    else:
        return_string = ""

    # If rec number needs to be truncated get the value
    # When no value is given default to 10,000 which should never be reached
    recs_to_truncate = form.cleaned_data["ignore_recs_over"]

    # TODO: Technically not every query needs the IIF statement
    # TODO: Including it just makes things easier to read and write
    # TODO: Find a clean way to split this up better for faster queries
    select_rec_score_string = f"IIF(anime_recs.recommendations > {recs_to_truncate}, {recs_to_truncate}"
    # If popularity compensation is enabled use an extra math string to compensate
    if request.GET.get("popularity_compensation"):
        math_string = "(anime.popularity + rec_anime.popularity)"
        select_rec_score_string += f".0 * {math_string}, anime_recs.recommendations * {math_string}"
    else:
        select_rec_score_string += f", anime_recs.recommendations"

    # If score compensation is enabled add it to the equation
    if request.GET.get("score_compensation"):
        # If there is no score given for an anime just use the average score for compensation
        select_rec_score_string += f" * IIF(user_anime.score = 0, {user.model.average_anime_score}, user_anime.score)"

    # Close up the string
    select_rec_score_string += "),"

    # Building the SQL query by hand to make it as fast as possible
    # This is by far the slowest part of the website so it needs to be as fast as possible
    sql_command = f"""  SELECT
                            anime_recs.recommended_media_id, 
                            anime_recs.media_id, 
                            {select_rec_score_string}
                            rec_anime.main_picture_medium, 
                            rec_anime.title, 
                            anime.title, 
                            -- Convert watching string to be more readable
                            rec_user_anime.status
                        FROM user_anime

                        -- Get information for the anime they have watched
                        INNER JOIN anime ON (user_anime.media_id = anime.id)\n"""

    if minimum_recs := request.GET.get("minimum_recs"):
        sql_command += f""" -- Get recs for this anime
                            INNER JOIN anime_recs ON (anime_recs.media_id = anime.id AND anime_recs.recommendations >= {minimum_recs})"""
    else:
        sql_command += """  -- Get recs for this anime
                            INNER JOIN anime_recs ON (anime_recs.media_id = anime.id)"""

    sql_command += f""" -- Get rec information
                        INNER JOIN anime rec_anime ON (anime_recs.recommended_media_id = rec_anime.id)

                        -- Get status for the recs
                        LEFT JOIN user_anime rec_user_anime ON (anime_recs.recommended_media_id = rec_user_anime.media_id AND rec_user_anime.user_id = {user.model.id})
                        
                        -- Only the specific media type for this user
                        WHERE ({status_in} AND user_anime.user_id = {user.model.id} {return_string}) """

    # Add sql command to the command list
    command += ["-sql", sql_command]

    # Add the number of results limiter to the command
    command += ["-number_of_results", str(form.cleaned_data["number_of_results"])]

    # If score compensation is enabled add it to the command
    if form.cleaned_data["score_compensation"]:
        command.append("score_compensation")

    jsoned = subprocess.run(command, stdout=PIPE, stderr=PIPE).stdout.decode()
    return HttpResponse(jsoned)


# TODO: Special response when dumb user disables all possible entries to use
# This is "fast enough" in the future I may try to offload some of this into a faster language
def recommendations(request: HttpRequest) -> HttpResponse:
    form = NameForm(request.GET)
    username = request.GET.get("username")
    user = MyAnimeListUser(username)
    if user.model_exists:
        # If there where missing anime entries last time the user visited the site update information
        if user.model.user_anime().count() != user.model.anime_count:
            modified_timestamp = datetime.now().astimezone()
            user.update_all(minimum_modified_timestamp=modified_timestamp)
            user.update_que_priority()
    else:
        if not ImportQue.objects.filter(type="user", key=username).first():
            ImportQue.objects.create(
                type="user", key=username, priority=10000, minimum_modified_timestamp=datetime.now().astimezone()
            )

    context = {
        "user": user,
        "form": form,
    }
    print(user.model.last_successful_anime_list_import)
    request.GET.get("username")
    return render(request, "main/recommendations.html", context)


def update(request: HttpRequest, username: str) -> HttpResponse:
    ImportQue.objects.get_or_create(
        type="user", key=username, priority=10000, minimum_info_timestamp=datetime.now().astimezone()
    )

    return redirect(f"/recommendations?username={username}&redirect=update")


def delete(request: HttpRequest, username: str) -> HttpResponse:
    user = MyAnimeListUser(username)
    user.model.delete()

    return redirect(f"/recommendations?username={username}&redirect=delete")
