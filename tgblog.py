# Copyright 2017 Kevin Froman - MIT License - https://ChaosWebs.net/
import sys, os, configparser, createDelete, subprocess, shutil, sqlite3, time, datetime, tgsocial, tgrss, tgplugins, tgls

markdownSupport = True # if the user has python markdown, which isn't standard library.
try:
    import markdown
except ImportError:
    markdownSupport = False

def getPostDate(title):
    # Get the post's date from database and return it (should be epoch format)
    conn = sqlite3.connect('.data/posts.db')
    c = conn.cursor()
    date = 0
    data = (title,)
    for row in c.execute('SELECT DATE FROM Posts where title=?', (data)):
        date = row[0]
    conn.close()
    return date

def updatePostList(title, add):
    # Add or remove a post from the database
    # add is either 'add' or 'remove'
    conn = sqlite3.connect('.data/posts.db')
    c = conn.cursor()
    if add == 'add':
        data = (title, str(int(time.time())))
        c.execute('INSERT INTO Posts (title, date) Values (?,?)', (data))
        status = ('success', 'Added post to database: ' + title)
    elif add == 'remove':
        data = (title,)
        c.execute('DELETE FROM Posts where TITLE = ?', (data))
        status = ('success', 'Removed post from database: ' + title)
    conn.commit()
    conn.close()

    return status

def rebuildIndex(config):
    # Rebuild the blog index.html file
    indexTemplate = 'source/blog-index.html'
    indexProdFile = 'generated/blog/index.html'
    conn = sqlite3.connect('.data/posts.db')
    content = ''
    postList = ''
    linesPreview = int(config['BLOG']['lines-preview'])
    previewText = ''
    previewFile = ''

    currentIndex = open(indexTemplate, 'r').read()

    c = conn.cursor()
    print('Rebuilding index...')

    # Get the posts form the database then build the HTML

    for row in c.execute('SELECT * FROM Posts ORDER BY ID DESC'):
        previewFile = open('source/posts/' + row[1] + '.html')
        previewText = previewFile.read()
        print('Adding ' + row[1] + ' to index...')
        postList = postList + '<a href="' + row[1] + '.html"><h2>' + row[1].replace('-', ' ').title() + '</h2></a>'
        postList = postList + '<div class="postDate">' + datetime.datetime.fromtimestamp(int(row[2])).strftime('%Y-%m-%d') + '</div>'
        postList = postList + '<div class="postPreview">'
        try:
            for x in range(0, linesPreview):
                if markdownSupport:
                    postList = postList + markdown.markdown(previewText.splitlines()[x])
                else:
                    postList = postList + previewText.splitlines()[x]
        except IndexError:
            pass
        previewFile.close()
        if linesPreview > 0:
            postList = postList + '<a href="' + row[1] + '.html">...</a>'
        postList = postList + '</div>'

    content = currentIndex.replace('[{SITETITLE}]', config['BLOG']['title'])
    content = content.replace('[{SITEDESC}]', config['BLOG']['description'])
    content = content.replace('[{AUTHOR}]', config['SITE']['AUTHOR'])
    content = content.replace('[{NAVBAR}]', '')
    content = content.replace('[{SITEFOOTER}]', config['BLOG']['footer'])
    content = content.replace('[{POSTLIST}]', postList)
    content = tgsocial.genSocial(config, content, 'post')

    f = open(indexProdFile, 'w').write(content)

    conn.close()

    return ('success', 'successfully rebuilt index')

def post(title, edit, config):
    # optionally edit, then, generate a blog post
    postExists = False
    if os.path.exists('source/posts/' + title + '.html'):
        postExists = True
    else:
        createDelete.createFile(title, 'post')
    editP = ''
    result = ''
    post = ''
    status = status = ('success', '')
    if not edit:
        date = getPostDate(title)
        date = datetime.datetime.fromtimestamp(int(date)).strftime('%Y-%m-%d')
    else:
        date = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d')
    if edit:
        # If recieved arg to edit the file
        try:
            editP = subprocess.Popen((os.getenv('EDITOR'), 'source/posts/' + title + '.html'))
            editP.wait()
        except TypeError:
            status = ('error', 'Unable to edit: ' + title + '. reason: editor environment variable is not set.')
    content = open('source/posts/' + title + '.html', 'r').read()
    if markdownSupport:
            content = markdown.markdown(content)

    template = open('source/blog-template.html', 'r').read()
    post = '[{PLUGINCONTENT}]' + tgplugins.events('blogEdit', template, config)
    post = post.replace('[{POSTTITLE}]', title.replace('-', ' ').title())
    post = post.replace('[{SITETITLE}]', config['BLOG']['title'])
    post = post.replace('[{AUTHOR}]', config['SITE']['author'])
    post = post.replace('[{POSTCONTENT}]', content)
    post = post.replace('[{SITEFOOTER}]', config['BLOG']['footer'])
    post = post.replace('[{NAVBAR}]', '')
    post = post.replace('[{SITEDESC}]', config['BLOG']['description'])
    post = post.replace('[{POSTDATE}]', date)
    post = post.replace('[{PLUGINCONTENT}]', '')
    post = tgsocial.genSocial(config, post, 'post')
    with open('generated/blog/' + title + '.html', 'w') as result:
        result.write(post)
    if status[1] != 'error':
        if not postExists:
            status = updatePostList(title, 'add')
            print(status[1])
            status = ('success', 'Successfully generated page: ' + title)
    return status
def blog(blogCmd, config):
    # Main blog command handler
    postTitle = ''
    status = ('success', '') # Return status. 0 = error or not, 1 = return message
    indexError = False # If command doesn't get an argument, don't try to generate
    fileError = False
    formatType = ''
    themeName = config['SITE']['theme']
    file = '' # file for rebuilding all operation
    if blogCmd == 'edit':
        try:
            postTitle = sys.argv[3].replace('<', '&lt;').replace('>', '&gt;')
            # Strip spaces from posts & replace with dashes, but only if the post does not already exist to preserve backwards compatability
            if not os.path.exists('source/posts/' + postTitle + '.html'):
                postTitle = postTitle.replace(' ', '-')
        except IndexError:
            status = ('error', 'syntax: blog edit "post title"')
            indexError = True
        if not indexError:
            #try:
            if postTitle.lower() == 'index':
                status = ('error', 'You cannot name a blog post \'index\'.')
            else:
                status = post(postTitle, True, config)
                shutil.copyfile('source/theme/' + themeName + '/theme.css', 'generated/blog/theme.css')
                if status[0] == 'success':
                    print(status[1]) # Print the status message of the last operation, generating the post. In this case it should be similar to 'successfully generated post'
                    print('Attempting to rebuild blog index...')
                    status = rebuildIndex(config) # Rebuild the blog index page
                    print('Rebuilding RSS feed')
                    print('Rebuilding images')
                    try:
                        shutil.rmtree('generated/blog/images/')
                    except FileNotFoundError:
                        pass
                    try:
                        shutil.rmtree('generated/images/')
                    except FileNotFoundError:
                        pass
                    if config['BLOG']['standalone'] == 'true':
                        shutil.copytree('source/theme/' + themeName + '/images/', 'generated/blog/images/')
                    else:
                        shutil.copytree('source/theme/' + themeName + '/images/', 'generated/images/')

                    tgrss.updateRSS(config)
    elif blogCmd == 'delete':
        try:
            postTitle = sys.argv[3]
        except IndexError:
            status = ('error', 'syntax: blog delete "post title"')
            indexError = True
        if not indexError:
            tgplugins.events('blogDelete', postTitle, config)
            try:
                createDelete.deleteFile(postTitle, 'posts')
            except FileNotFoundError:
                status = ('error', 'Error encountered while deleting: ' + postTitle + ' reason: post does not exist')
                fileError = True
            except Exception as e:
                status = ('error', 'Error encountered while deleting: ' + postTitle + ': ' + str(e))
                fileError = True
            if not fileError:
                try:
                    status = updatePostList(postTitle, 'remove')
                except Exception as e:
                    status = ('error', 'error occured removing post from database: ' + str(e))
                status = rebuildIndex(config)
    elif blogCmd == 'list':
        print('Listing posts...')
        tgls.listFiles('posts')
    elif blogCmd == 'rebuild':
        # Rebuild all blog posts and assets
        tgplugins.events('blogRebuild', '', config)
        shutil.copyfile('source/theme/' + themeName + '/theme.css', 'generated/blog/theme.css')
        try:
            shutil.rmtree('generated/images/')
        except FileNotFoundError:
            pass
        try:
            shutil.rmtree('generated/blog/images/')
        except FileNotFoundError:
            pass
        if config['BLOG']['standalone'] == 'true':
            shutil.copytree('source/theme/' + themeName + '/images/', 'generated/blog/images/')
        else:
            shutil.copytree('source/theme/' + themeName + '/images/', 'generated/images/')
        print('Rebuilding posts')
        for file in os.listdir('generated/blog/'):
            if file.endswith('.html'):
                if file != 'index.html':
                    file = file[:-5].strip()
                    try:
                        post(file, False, config)
                    except PermissionError:
                        print('Could not rebuild ' + file + '. Reason: Permission error')
                    except Exception as e:
                        print('Could not rebuild ' + file + '. Reason: ' + str(e))
        print('Rebuilding RSS feed')
        tgrss.updateRSS(config)
        print('Successfully rebuilt all posts.')
        # Rebuild index includes its own message about rebuilding
        rebuildIndex(config)
        status = ('success', 'Rebuild successful')
    elif blogCmd == '':
        status = ('success', '')
    else:
        status = ('error', 'Invalid blog command')
    return status
