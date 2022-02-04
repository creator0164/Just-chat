from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_text
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import login, authenticate, logout
from django.conf import settings
from account.models import Account
from friend.models import FriendList, FriendRequest

from django.core.files.storage import default_storage
from django.core.files.storage import FileSystemStorage
import os
import cv2
import json
import base64

from django.core import files
from friend.utils import get_friend_request_or_false
from friend.friend_request_status import FriendRequestStatus
from account.forms import RegistrationForm, AccountAuthenticationForm, AccountUpdateForm

TEMP_PROFILE_IMAGE_NAME = "temp_profile_image.png"


def register_view(request, user_http=False, *args, **kwargs):
    user = request.user
    current_site = get_current_site(request)
    if request.is_secure():
        user_http = True
    if user.is_authenticated:
        return HttpResponse(f'You are already authenticated as {user.email}.')
    context = {}

    if request.POST:
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            email = request.POST['email']
            user_email = Account.objects.get(email=email)
            subject = 'Email Confirmation From JustChat'
            message = render_to_string('account/email_send/email_send.html', {
                'protocol': 'https' if user_http else 'http',
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user_email.pk)),
                'token': default_token_generator.make_token(user_email),
                'email': email,
            })
            email_send = EmailMessage(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [email],
            )
            email_send.fail_silently = False
            email_send.send()
            return redirect('password_reset_done')
        else:
            context['registration_form'] = form
    else:
        form = RegistrationForm()
        context['registration_form'] = form

    return render(request, 'account/register.html', context)


def logout_view(request):
    logout(request)
    return redirect("home")


def login_view(request, *args, **kwargs):
    context = {}

    user = request.user
    if user.is_authenticated:
        return redirect("home")

    destination = get_redirect_if_exists(request)

    if request.POST:
        form = AccountAuthenticationForm(request.POST)
        if form.is_valid():
            email = request.POST['email']
            password = request.POST['password']
            user = authenticate(
                email=email, password=password)

            if user:
                login(request, user)
                if destination:
                    return redirect(destination)
                return redirect("home")

    else:
        form = AccountAuthenticationForm()

    context['login_form'] = form

    return render(request, "account/login.html", context)


def get_redirect_if_exists(request):
    redirect = None
    if request.GET:
        if request.GET.get("next"):
            redirect = str(request.GET.get("next"))
    return redirect


def account_view(request, *args, **kwargs):
    """
        - Logic here is kind of tricky
                is_self
                is_friend
                        -1: NO_REQUEST_SENT
                        0: THEM_SENT_TO_YOU
                        1: YOU_SENT_TO_THEM
    """
    context = {}
    user_id = kwargs.get('user_id')
    try:
        account = Account.objects.get(pk=user_id)
    except:
        return HttpResponse("That user doesn't exist.")

    if account:
        context['id'] = account.id
        context['username'] = account.username
        context['email'] = account.email
        context['profile_image'] = account.profile_image.url
        context['hide_email'] = account.hide_email

        try:
            friend_list = FriendList.objects.get(user=account)
        except FriendList.DoesNotExist:
            friend_list = FriendList(user=account)
            friend_list.save()
        friends = friend_list.friends.all()
        context['friends'] = friends

        is_self = True
        is_friend = False
        request_sent = FriendRequestStatus.NO_REQUEST_SENT.value
        friend_requests = None
        user = request.user
        if user.is_authenticated and user != account:
            is_self = False
            if friends.filter(pk=user.id):
                is_friend = True
            else:
                is_friend = False

                # CASE 1: Request has been sent from THEM to YOU:
                #         FriendRequestStatus.THEM_SENT_TO_YOU
                if get_friend_request_or_false(sender=account, receiver=user) != False:
                    request_sent = FriendRequestStatus.THEM_SENT_TO_YOU.value
                    context['pending_friend_request_id'] = get_friend_request_or_false(
                        sender=account, receiver=user).id
                # CASE 2: Request has been sent from YOU to THEM:
                #         FrienRequestStatus.YOU_SENT_TO_THEM
                elif get_friend_request_or_false(sender=user, receiver=account) != False:
                    request_sent = FriendRequestStatus.YOU_SENT_TO_THEM.value
                # CASE 3: No request has been sent. FriendRequestStatus.NO_REQUEST_SENT
                else:
                    request_sent = FriendRequestStatus.NO_REQUEST_SENT.value

        elif not user.is_authenticated:
            is_self = False
        else:
            try:
                friend_requests = FriendRequest.objects.filter(
                    receiver=user, is_active=True)
            except:
                pass
        context['is_self'] = is_self
        context['is_friend'] = is_friend
        context['request_sent'] = request_sent
        context['friend_requests'] = friend_requests
        context['BASE_URL'] = settings.BASE_URL

        return render(request, "account/account.html", context)


def account_search_view(request, *args, **kwargs):
    context = {}

    if request.method == 'GET':
        search_query = request.GET.get('q')
        if len(search_query) > 0:
            search_results = Account.objects.filter(email__icontains=search_query).filter(
                username__icontains=search_query).distinct()
            user = request.user
            # Store lahat ng account na nasearch friends or hindi.
            accounts = []
            if user.is_authenticated:
                # Get authenticated user friend list
                auth_user_friend_list = FriendList.objects.get(user=user)
                for account in search_results:
                    # Wala kang friends
                    accounts.append(
                        (account, auth_user_friend_list.is_mutual_friend(account)))
                context['accounts'] = accounts
            else:
                for account in search_results:
                    accounts.append((account, False))  # Wala kang friends
                context['accounts'] = accounts

    return render(request, 'account/search_results.html', context)


def edit_account_view(request, *args, **kwargs):
    if not request.user.is_authenticated:
        return redirect('login')

    user_id = kwargs.get('user_id')
    try:
        account = Account.objects.get(pk=user_id)
    except Account.DoesNotExist:
        return HttpResponse('Something went wrong.')

    if account.pk != request.user.pk:
        return HttpResponse('You cannot edit someone elses profile.')
    context = {}

    if request.POST:
        form = AccountUpdateForm(
            request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('view', user_id=account.pk)
        else:
            form = AccountUpdateForm(request.POST, instance=request.user,

                                     initial={
                                         'id': account.pk,
                                         'email': account.email,
                                         'username': account.username,
                                         'profile_image': account.profile_image,
                                         'hide_email': account.hide_email,
                                     })
    else:
        form = AccountUpdateForm(request.POST, instance=request.user,

                                 initial={
                                     'id': account.pk,
                                     'email': account.email,
                                     'username': account.username,
                                     'profile_image': account.profile_image,
                                     'hide_email': account.hide_email,
                                 })
        context['form'] = form
    context['DATA_UPLOAD_MAX_MEMORY_SIZE'] = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    return render(request, 'account/edit_account.html', context)


def save_temp_profile_image_from_base64String(imageString, user):
    INCORRECT_PADDING_EXCEPTION = 'Incorrect padding'
    try:
        if not os.path.exists(settings.TEMP):
            os.mkdir(settings.TEMP)
        if not os.path.exists(f'{settings.TEMP}/{user.pk}'):
            os.mkdir(f'{settings.TEMP}/{user.pk}')
        url = os.path.join(f'{settings.TEMP}/{user.pk}',
                           TEMP_PROFILE_IMAGE_NAME)
        storage = FileSystemStorage(location=url)
        image = base64.b64decode(imageString)

        with storage.open('', 'wb+') as destination:
            destination.write(image)
            destination.close()

        return url

    except Exception as e:
        if str(e) == INCORRECT_PADDING_EXCEPTION:
            imageString += '=' * ((4 - len(imageString) % 4) % 4)

            return save_temp_profile_image_from_base64String(imageString, user)

    return None


def crop_image(request, *args, **kwargs):
    payload = {}
    user = request.user

    if request.POST and user.is_authenticated:
        try:
            imageString = request.POST.get('image')
            url = save_temp_profile_image_from_base64String(imageString, user)
            img = cv2.imread(url)

            cropX = int(float(str(request.POST.get('cropX'))))
            cropY = int(float(str(request.POST.get('cropY'))))
            cropWidth = int(float(str(request.POST.get('cropWidth'))))
            cropHeight = int(float(str(request.POST.get('cropHeight'))))

            if cropX < 0:
                cropX = 0
            if cropY < 0:
                cropY = 0

            crop_img = img[cropY:cropY + cropHeight, cropX:cropX + cropWidth]
            cv2.imwrite(url, crop_img)
            user.profile_image.delete()
            user.profile_image.save(
                'profile_image.png', files.File(open(url, 'rb')))
            user.save()

            payload['result'] = 'success'
            payload['cropped_profile_image'] = user.profile_image.url

            os.remove(url)

        except Exception as e:
            payload['result'] = 'error'
            payload['result'] = str(e)

    return HttpResponse(json.dumps(payload), content_type='application/json')


def email_activation(request, uidb64, token):
    try:
        t1 = 'not'
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account.objects.get(pk=uid)
        if default_token_generator.check_token(user, token):
            t1 = 'OK'
            user.is_active = True
            user.save()
    except Account.DoesNotExist:
        return HttpResponse('This activation link already used.')
    except:
        return HttpResponse('Activation fail please try again later.')

    return HttpResponse(f'{user.email} You are now authenticated. Try to login to JustChat')
